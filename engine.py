from schema_builder import build_schema, ACCEPT_NODE, print_schema_storage, SchemaRef
from token_gen import token_stream
from error_log import ValidationResult, ValidationError, ErrorType, ValidationLog
from validators import ValidationEngine
from constants import NodeType, schema_file
from circuit_breaker import CircuitBreaker, CircuitBreakerException
from constants import get_fingerprint_obj, get_fingerprint_arr
from pathlib import Path

class Node:
    def __init__(self, key=None):
        self.key = key
        self.value = None # primitive only
        # self.state = ValidationStatus.VALID # stores the results of validation using necessary schemas
        
        self.errors = ValidationResult()
        self.parent = None
        self.type = NodeType.Object # OBJECT / ARRAY / VALUE
        self.children = None # dict or list

        self.schema_id = 0

        self.my_schema_id_lst = [SchemaRef(0)]
        self.my_states = []

        self.children_schema_id_lst = [SchemaRef(0)]
        self.child_states = [[]] # stores the extra states from children, a list validationResult

    def __eq__(self, other):
        if not isinstance(other, Node):
            return False
        if self.type != other.type:
            return False
        if self.type == NodeType.Value:
            return self.value == other.value
        if self.children.keys() != other.children.keys():
            return False
        else:
            return all(self.children[k] == other.children[k] for k in self.children.keys())

    def content(self):
        # print(self.my_states)
        for i in range(len(self.my_schema_id_lst)):
            if len(self.my_states) > i and self.my_states[i]:
                print(f'schema id: {self.my_schema_id_lst[i].value()}')
                print(self.my_states[i])
        
    def get_path(self):
        parts = []
        node = self

        while node.parent is not None:
            if node.parent.type == NodeType.Array:
                parts.append(f'[{node.key}]')
            else:
                parts.append(f'.{node.key}')
            node = node.parent

        return ''.join(reversed(parts)).lstrip('.')

    def __repr__(self):
        value = ''
        if self.type is NodeType.Value:
            value = f'Value[{self.value}]'
        elif self.children is not None:
            if self.type is NodeType.Object:
                value = f'Object[{', '.join(self.children.keys())}]'
            elif self.type is NodeType.Array:
                child_str = [str(x) for x in self.children.values()]
                value = f'Array[{', '.join(child_str)}]'

        return f'{value}'

    def set_schema(self, id):
        self.schema_id = id

    def set_value(self, value):
        self.value = value

    def add_child(self, node):
        if self.children is None:
            self.children = {}
        if self.type is NodeType.Array:
            idx = len(self.children) 
            node.key = idx
            self.children[idx] = node
        else:
            self.children[node.key] = node

    def remove_child(self, node):
        if self.children is None or node.key not in self.children.keys():
            raise ValueError('fail to remove the child')
        
        # calculate the fingerprint of the child node and store it in the parent node's children dict
        if node.type is NodeType.Object:
            node.value = get_fingerprint_obj(node.children)
        if node.type is NodeType.Array:
            node.value = get_fingerprint_arr(node.children.values())

        # self.children.pop(node.key)
        # if the node is of type Value, stores its value directly
        self.children[node.key] = node.value
        # print(f'[{self}]remove child: {node.value}')

    def add_value(self, value):
        if self.type is NodeType.Value:
            self.set_value(value)
       
        else:
            # print(f'wrong type: {self.type}')
            raise TypeError()
        
    def register_state(self, node):

        if node.key not in self.children.keys():
            raise ValueError('wrong register: not a child of its parent')
        assert len(node.my_states) == len(self.child_states)
        for i in range(len(node.my_states)):
            self.child_states[i].append(node.my_states[i])

class Engine():
    def __init__(self, schema=None, target=None, max_depth=None, log_file_name=None):
        # set up logging
        self.logs = ValidationLog(log_file_name)
            
        # set up stack
        self.stack = [Node('root')] # adding a dummy node to eliminate the need of boundary checking

        self.schema_storage = build_schema(Path(schema).resolve()) if schema is not None else None
        self.token_stream = token_stream(Path(target).resolve()) if target is not None else None
        self.validators = ValidationEngine(self.schema_storage)
        self.circuit_breaker = CircuitBreaker(max_depth)

        self.current_node = self.stack[0]

    def push(self, node):
        # bind the node with its schema

        # print(f'push: {node.get_path()}')
        # print(f'node parent: {node.parent}')

        node.my_schema_id_lst = self.validators.collect_schemas_for_me(node.parent.children_schema_id_lst, node.key)
        node.children_schema_id_lst = self.validators.collect_schemas_for_children(node.my_schema_id_lst)

        # multiple schemas
        
        node.child_states = [[] for _ in range(len(node.children_schema_id_lst))]


        self.current_node = node
        self.stack.append(node)
        self.circuit_breaker.on_push()

    def pop(self):
        node = self.stack.pop()
        self.circuit_breaker.on_pop()
        if node.parent is None:
            raise ValueError('standalone node')
        # print('----------------')
        # print(f'pop node: {node}')
        # print(f'pop: {node.get_path()}')
        # print(f'my content: {node.content()}')
        self.verify_node(node)

        # after verifying the node, register its state to the parent node
        # then remove it from the children dict
        node.parent.register_state(node)
        node.parent.remove_child(node)

        # move the current force to its parent, which is to be 
        self.current_node = node.parent

        for i in range(len(node.my_schema_id_lst)):
            if node.my_states[i]:
                self.logs.add_log(node.my_states[i], node.get_path(), str(node))
        
        return node
    
    def force_pop(self):
        if len(self.stack) == 1:
            raise ValueError('cannot pop the root node')
        unclose_error = ValidationResult(ValidationError(ErrorType.UNCLOSED))
        while(len(self.stack) > 1):
            node = self.stack.pop()
            if len(node.my_states) == 0:
                node.my_states.append(unclose_error)
            else:
                for s in node.my_states:
                    s += unclose_error

            for i in range(len(node.my_schema_id_lst)):
                if node.my_states[i]:
                    self.logs.add_log(node.my_states[i], node.get_path(), str(node))

            node.parent.register_state(node)
            
    def verify_node(self, node: Node):
        if node.type is NodeType.Value:
            for schema_id in node.my_schema_id_lst:
                node.my_states.append(self.validators.validate_schema(schema_id, node.value))

        elif node.type is NodeType.Object:
            for schema_id in node.my_schema_id_lst:
                node.my_states.append(self.validators.validate_schema(schema_id, node.children, node.child_states))

        elif node.type is NodeType.Array:
            for schema_id in node.my_schema_id_lst:
                node.my_states.append(self.validators.validate_schema(schema_id, list(node.children.values()), node.child_states))

    def create_new_node(self, type, key=None):
        node = Node(key)
        node.type = type
        node.parent = self.current_node
        
        node.parent.add_child(node)
        self.current_node = node
        self.push(node)

        return node
            
    def run(self):
        pending_key = None

        try:
            for token in self.token_stream:
                if token.is_start_object():
                    if pending_key is None and len(self.stack) == 1:
                        key = 'top_object'
                    
                    elif self.current_node.type == NodeType.Array:
                        key = len(self.current_node.children) if self.current_node.children else 0
                    else:
                        key = pending_key
                    
                    node = self.create_new_node(NodeType.Object, key)
                    # node.parent.add_child(node)
                    pending_key = None

                if token.is_start_array():
                    node = self.create_new_node(NodeType.Array, pending_key)
                    pending_key = None

                if token.is_end_object():
                    self.pop()

                if token.is_end_array():
                    self.pop()

                if token.is_key():
                    pending_key = token.content

                if token.is_value():
                    value = token.content
                    parent = self.current_node

                    # if it is in an array
                    if parent.type is NodeType.Array:
                        # print(f'pushing child into array object {parent}->{value}')
                        node = self.create_new_node(NodeType.Value)
                        node.add_value(value)

                    else:
                        # it is in an object
                        node = self.create_new_node(NodeType.Value, pending_key)
                        node.add_value(value)
                        pending_key = None

                    node = self.pop()
            
            # if stack has remaining nodes, they are not closed, force pop them
            if len(self.stack) > 1:
                self.force_pop()
        
        except CircuitBreakerException as e:
            self.logs.add_log(ValidationError(ErrorType.DEPTH_ERROR, {'depth': self.circuit_breaker.maximum_allowed_depth}), 
                              'circuit_breaker')
            
        except Exception as e:
            print(f'error! {e}')
        finally:
            self.logs.report(self.circuit_breaker.max_recorded_depth)
            top_obj_state = self.stack[0]
            
            if len(top_obj_state.child_states[0]) == 0:
                return True, "invalid"
            else:
                return bool(top_obj_state.child_states[0][0]), top_obj_state.child_states[0][0].state()

if __name__ == '__main__':
    engine = Engine(schema=schema_file, target='data_unclosed_error.json', log_file_name='validation_log.txt', max_depth=10)
    engine.run()