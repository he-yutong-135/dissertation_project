from schema_builder import build_schema, ACCEPT_NODE
from token_gen import token_stream
from validators import ValidationStatus, ValidationEngine
from constants import NodeType, schema_file, data_file, ValidationError, ErrorType, dent
from circuit_breaker import CircuitBreaker, CircuitBreakerException
import logging


class Node:
    def __init__(self, key=None):
        self.key = key
        self.value = None # primitive only
        self.state = ValidationStatus.VALID
        self.errors = []
        self.parent = None
        self.type = NodeType.Object # OBJECT / ARRAY / VALUE
        self.children = None # dict or list

        self.children_states = None # this records the validation status of each child node

        self.schema_id = 0

    def is_valid(self):
        return self.state == ValidationStatus.VALID
    
    def content(self):
        if self.type == NodeType.Value:
            return self.value
        else:
            return self.children_states
        
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
            value = f': value({self.value})'
        elif self.children is not None:
            if self.type is NodeType.Object:
                value = f': children({self.children.keys()})'
            elif self.type is NodeType.Array:
                value = f': array({self.children.items()})'

        schema = f'schema({self.schema_id})' 
        # errors = '' if len(self.errors) == 0 else '\n'.join(str(e) for e in self.errors)
        return f'Node[{self.type}|{self.key} {value}] -> {schema} state({self.state})'

    def set_schema(self, id):
        self.schema_id = id

    def set_value(self, value):
        # if self.type != "value":
        #     raise TypeError()

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

        self.children.pop(node.key)

    def add_value(self, value):
        if self.type is NodeType.Value:
            self.set_value(value)
       
        else:
            print(f'wrong type: {self.type}')
            raise TypeError()
        
    def register_state(self, node):
        if self.children_states is None:
            self.children_states = {}

        if node.key not in self.children.keys():
            raise ValueError('wrong register: not a child of its parent')

        self.children_states[node.key] = node.state

class Engine():
    def __init__(self, schema=None, target=None, max_depth=None, log_file_name=None):
        # set up logging
        if log_file_name is None:
            self.log_file_name = f"{target[:-5]}_{schema[:-5]}_validation.log"
        else:
            self.log_file_name = log_file_name

        self.logger = logging.getLogger(self.log_file_name) 
        self.logger.setLevel(logging.ERROR)

        if not self.logger.handlers:
            handler = logging.FileHandler(self.log_file_name, mode='w', encoding='utf-8')
            formatter = logging.Formatter('%(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        self.stack = [Node('root')] # adding a dummy node to eliminate the need of boundary checking

        self.schema_storage = build_schema(schema) if schema is not None else None
        self.token_stream = token_stream(target) if target is not None else None
        self.validators = ValidationEngine(self.schema_storage)
        self.circuit_breaker = CircuitBreaker(max_depth)

        self.current_node = self.stack[0]
        self.current_schema_id = ACCEPT_NODE.id# self.schema_storage[0] # starting schema for outermost json object

    def change_schema(self, file_name):
        self.schema_storage = build_schema(file_name)
        self.current_schema_id = ACCEPT_NODE.id

    def change_target(self, file_name):
        self.token_stream = token_stream(file_name)

    def push(self, node):
        child_schema_id = self.validators.find_child(self.current_schema_id, node.key)
        node.schema_id = child_schema_id

        self.current_node = node
        self.current_schema_id = node.schema_id
        # print(f'push: {node}')
        self.stack.append(node)
        self.circuit_breaker.on_push()

    def pop(self):
        node = self.stack.pop()
        self.circuit_breaker.on_pop()
        if node.parent is None:
            raise ValueError('standalone node')
        
        self.verify_node(node)

        # after verifying the node, register its state to the parent node
        # then remove it from the children dict
        node.parent.register_state(node)
        # node.parent.remove_child(node)

        # move the current force to its parent, which is to be 
        self.current_node = node.parent
        self.current_schema_id = node.parent.schema_id
        # print(f'pop: {node}')
        if not node.is_valid():
            self.logger.error(f'- invalid json item: path({node.get_path()})')
            self.logger.error(f'{dent}node info: {node.content()}')
            for e in node.errors:
                self.logger.error(f'{dent}{e}')
            self.logger.error(f'-' * 120)

        return node
    
    def force_pop(self):
        if len(self.stack) == 1:
            raise ValueError('cannot pop the root node')
        unclose_error = ValidationError(ErrorType.UNCLOSED, 'unclosed structure')
        self.logger.error(f'Validation incomplete: unclosed structure')
        while(len(self.stack) > 1):
            node = self.stack.pop()
            # print(f'force pop: {node}')
            self.logger.error(f'- unclosed json item: path({node.get_path()})')
            self.logger.error(f'{dent}node info: {node.content()}')
            for e in node.errors:
                self.logger.error(f'{dent}{e}')
            self.logger.error(f'{dent}{unclose_error}')
            self.logger.error('-' * 120)

    def verify_node(self, node: Node):
        if node.type is NodeType.Value:
            node.state, node.errors = self.validators.validate_value(node.schema_id, node.value)

        if node.type is NodeType.Object:
            node.state, node.errors = self.validators.validate_object_complete(node.schema_id, node.children_states)

        if node.type is NodeType.Array:
            node.state, node.errors = self.validators.validate_array_complete(node.schema_id, node.children_states)
            
    def create_new_node(self, type, key=None):
        node = Node(key)
        node.type = type
        node.parent = self.current_node
        
        node.parent.add_child(node)
        self.current_node = node
        self.push(node)

        return node
            
    def run(self):
        # clear the log file before writing
        with open(self.log_file_name, 'w'): pass
        self.logger.error(f'--- Validation Error Log ---')
        self.logger.error('-' * 120)
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
            
        except CircuitBreakerException as e:
            self.logger.error(f"Circuit breaker activated: {e}")
            # print(self.stack[-1].get_path())
            
        finally:
            if len(self.stack) > 1:
                self.force_pop()
            self.logger.error(f'(maximum stack depth: {self.circuit_breaker.max_recorded_depth})')
            self.logger.error('--- validation done ---')
            for handler in self.logger.handlers[:]:
                handler.close()
                self.logger.removeHandler(handler)

        return self.log_file_name

if __name__ == '__main__':
    engine = Engine(schema=schema_file, target='data_unclosed_error.json')
    log_file = engine.run()
    print(f'Validation log saved to: {log_file}')
