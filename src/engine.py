from .schema_builder import build_schema, SchemaRef
from .token_gen import token_stream
from .error_log import ValidationResult, ValidationError, ErrorType, ValidationLog, ValidationResNoLog
from .validators import ValidationEngine
from .constants import NodeType, get_fingerprint_obj, get_fingerprint_arr, needs_log
from .circuit_breaker import CircuitBreaker, CircuitBreakerException
import traceback

NodeValidationRes = ValidationResult if needs_log else ValidationResNoLog

class Node:
    def __init__(self, key=None):
        self.key = key
        self.value = None # primitive only
        self.line = None
        self.parent = None
        self.type = NodeType.Object # OBJECT / ARRAY / VALUE
        self.children = {} # dict or list

        self.my_schema_id_lst = [SchemaRef(0)]
        self.my_states = []

        self.children_schema_id_lst = [(None, SchemaRef(0))]
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
        value = f'{self.type}'
        if self.type is NodeType.Object and self.children:
            value += f'[{', '.join(self.children.keys())}]'
        elif self.type is NodeType.Array and self.children:
            child_str = [str(x) for x in self.children.values()]
            value += f'[{', '.join(child_str)}]'
        else:
            value += f'[{self.value}]'
        return value

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
        # if the node is of type Value, stores its value directly
        self.children[node.key] = node.value

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

        self.schema_storage, self.anchor_storage, self.id_storage = build_schema(schema)
        self.token_stream = token_stream(target)
        self.validators = ValidationEngine(self.schema_storage, self.anchor_storage, self.id_storage)
        self.circuit_breaker = CircuitBreaker(max_depth)

        self.current_node = self.stack[0]

    def push(self, node):

        # bind the node with its schema
        schema_id_lst = self.validators.collect_schemas_for_me(node.parent.children_schema_id_lst, node.key)
        if schema_id_lst is not None:
            node.my_schema_id_lst = schema_id_lst
        node.children_schema_id_lst = self.validators.collect_schemas_for_children(node.my_schema_id_lst, node.type)

        # multiple schemas
        node.child_states = [[] for _ in range(len(node.children_schema_id_lst))]

        self.current_node = node
        self.stack.append(node)
        self.circuit_breaker.on_push()

    def pop(self, end_line):
        node = self.stack.pop()
        # ref = weakref.ref(node)
        self.circuit_breaker.on_pop()
        if node.parent is None:
            raise ValueError('standalone node')
        self.verify_node(node)

        # after verifying the node, register its state to the parent node
        # then remove it from the children dict
        node.parent.register_state(node)
        node.parent.remove_child(node)

        # move the current force to its parent, which is to be 
        self.current_node = node.parent
        my_errors = NodeValidationRes()
        node.line = (node.line, end_line)
        for i in range(len(node.my_schema_id_lst)):
            if not node.my_states[i]:
                my_errors += node.my_states[i]
                self.logs.add_log(node.my_states[i], node.get_path(), str(node), node.line)

        node.parent = None # break the reference to its parent 
        node.children = None # break the reference to its children
        node.my_states = None
        node.child_states = None
        node = None

    def force_pop(self, end_line):
        unclose_error = NodeValidationRes(ValidationError(ErrorType.UNCLOSED))
        while(len(self.stack) > 1):
            node = self.stack.pop()
            node.line = (node.line, end_line)
            if len(node.my_states) == 0:
                node.my_states.append(unclose_error)
            else:
                for s in node.my_states:
                    s += unclose_error

            for i in range(len(node.my_schema_id_lst)):
                if not bool(node.my_states[i]):
                    self.logs.add_log(node.my_states[i], node.get_path(), str(node), node.line)

            node.parent.register_state(node)
            
    def verify_node(self, node: Node):
        my_value = None
        
        if node.type is NodeType.Object:
            node.set_value(get_fingerprint_obj(node.children))
            my_value = node.children

        elif node.type is NodeType.Array:
            node.set_value(get_fingerprint_arr(node.children.values()))  
            my_value = list(node.children.values())

        else:
            my_value = node.value
        # verify each schema iteratively            
        for schemas in node.my_schema_id_lst:
                
            if isinstance(schemas, tuple):
                validationRes = NodeValidationRes()
                for schema_id in schemas:
                    validationRes += self.validators.validate_schema(schema_id, my_value, node.child_states, my_type=node.type)
                node.my_states.append(validationRes)  

            elif isinstance(schemas, SchemaRef):
                node.my_states.append(self.validators.validate_schema(schemas, my_value, node.child_states, my_type=node.type))

            else:
                # if schema is a boolean or ValidationState, no need for verification, append directly
                node.my_states.append(schemas)

    def create_new_node(self, type, key=None, line=None):
        if key is not None: node = Node(key)
        else: node = Node(type) # if no key provided, use its type as the default key
        node.type = type
        node.line = line
        node.parent = self.current_node
        
        node.parent.add_child(node)
        self.current_node = node
        self.push(node)

        return node
            
    def run(self):
        pending_key = None
        type = NodeType.Object
        last_line = None
        try:
            for token in self.token_stream:
                last_line = token.line
                if token.is_start_object():
                    if pending_key is None and len(self.stack) == 1:
                        key = 'top_object'
                    
                    elif self.current_node.type == NodeType.Array:
                        key = len(self.current_node.children) if self.current_node.children else 0
                    else:
                        key = pending_key
                    
                    node = self.create_new_node(NodeType.Object, key, token.line)
                    # node.parent.add_child(node)
                    pending_key = None

                if token.is_start_array():
                    node = self.create_new_node(NodeType.Array, pending_key, token.line)
                    pending_key = None

                if token.is_end_object():
                    self.pop(token.line)

                if token.is_end_array():
                    self.pop(token.line)

                if token.is_key():
                    pending_key = token.content

                if token.is_value():
                    value = token.content
                    parent = self.current_node

                    # decide the type of the value
                    # type = None
                    if value is None:
                        type = NodeType.Null
                    elif isinstance(value, bool):
                        type = NodeType.Boolean
                    elif isinstance(value, int):
                        type = NodeType.Integer
                    elif isinstance(value, float):
                        type = NodeType.Number
                    elif isinstance(value, str):
                        type = NodeType.String

                    # if it is in an array
                    if parent.type is NodeType.Array:
                        node = self.create_new_node(type, line=token.line)
                        node.set_value(value)
                    else:
                        # it is in an object
                        node = self.create_new_node(type, pending_key, line=token.line)
                        node.set_value(value)
                        pending_key = None
                    self.pop(token.line)
            
            # if stack has remaining nodes, they are not closed, force pop them
            if len(self.stack) > 1:
                self.force_pop(last_line)

        except CircuitBreakerException as e:
            depth_error = NodeValidationRes(ValidationError(ErrorType.DEPTH_ERROR, {'depth': self.circuit_breaker.maximum_allowed_depth}))
            self.logs.add_log(depth_error, self.current_node.get_path(), str(self.current_node), line=self.current_node.line)
            self.stack[0].child_states[0].append(depth_error)
            
        except Exception as e:
            traceback.print_exc()
            error = NodeValidationRes(ValidationError(ErrorType.UNEXPECTED, {'value': f'runtime error: \n{e}'}))
            self.logs.add_log(error, self.current_node.get_path(), str(self.current_node), line=self.current_node.line)
            self.stack[0].child_states[0].append(error)
        finally:
            self.logs.report(self.circuit_breaker.max_recorded_depth)
            top_obj_state = self.stack[0]
            
            if len(top_obj_state.child_states[0]) == 0:
                return True, "valid"
            else:
                return bool(top_obj_state.child_states[0][0]), top_obj_state.child_states[0][0].state()
