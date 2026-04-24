from schema_builder import build_schema, ACCEPT_NODE, to_primitive
from token_gen import token_stream, print_token_stream, TokenType
import configparser
from validators import ValidationStatus, ValidationEngine
from constants import NodeType, schema_file, data_file

class Node:
    def __init__(self, key=None):
        self.key = key
        self.value = None # primitive only
        self.state = ValidationStatus.VALID
        self.parent = None
        self.type = NodeType.Object # OBJECT / ARRAY / VALUE
        self.children = None # dict or list

        self.children_states = None # this records the validation status of each child node

        self.schema_id = 0

    # def is_valid(self):
    #     return self.state == ValidationStatus.VALID 

    def __repr__(self):
        value = ''
        if self.value is not None:
            value = f': value({self.value})'
        elif self.children is not None:
            if self.type is NodeType.Object:
                value = f': children({self.children_states})'
            elif self.type is NodeType.Array:
                value = f': array({self.children_states})'

        schema = f'schema({self.schema_id})' 
        return f'[{self.type}| {self.key}{value}] -> {schema} state({self.state})'

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
        # elif self.type is NodeType.Array:
        #     self.add_element(value)
        # elif self.type is NodeType.Object:
        #     self.add_child(value) 
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
    def __init__(self, schema=None, target=None):
        # self.dummy_node = Node('root')
        self.stack = [Node('root')] # adding a dummy node to eliminate the need of boundary checking
        self.schema_storage = build_schema(schema) if schema is not None else None
        self.token_stream = token_stream(target) if target is not None else None
        self.validators = ValidationEngine(self.schema_storage)

        self.current_node = self.stack[0]
        self.current_schema_id = ACCEPT_NODE.id# self.schema_storage[0] # starting schema for outermost json object

    def change_schema(self, file_name):
        self.schema_storage = build_schema(file_name)
        self.current_schema_id = ACCEPT_NODE.id

    def change_target(self, file_name):
        self.token_stream = token_stream(file_name)

    def push(self, node):
        # print(f'pushing node {node} with current_schema: {self.current_schema_id}')

        # self.current_schema.accept_child(node.key)
    
        child_schema_id = self.validators.find_child(self.current_schema_id, node.key)
        # self.current_schema.find_child_schema(node.key)
        node.schema_id = child_schema_id
        # print(f'push: {node} with schema id: {child_schema_id}')

        self.current_node = node
        self.current_schema_id = node.schema_id
        self.stack.append(node)

    def pop(self):
        node = self.stack.pop()
        
        
        # if len(self.stack) > 0 and node.parent is None:
        if node.parent is None:
            raise ValueError('standalone node')
        
        self.verify_node(node)

        # after verifying the node, register its state to the parent node
        # then remove it from the children dict
        node.parent.register_state(node)
        node.parent.remove_child(node)

        # move the current force to its parent, which is to be 
        self.current_node = node.parent
        self.current_schema_id = node.parent.schema_id
        # self.display_stack()
        print(f'pop: {node}')

        return node

    def verify_node(self, node: Node):
        if node.type is NodeType.Value:
            node.state = self.validators.validate_value(node.schema_id, node.value)

        else:
            node.state = self.validators.validate_complete(node.schema_id, node.children_states)

    def verify_structure(self, node):
        if node.key is None:
            raise ValueError(f'key is none:')
        
        return True
            
    def create_new_node(self, type, key=None):
        node = Node(key)
        node.type = type
        node.parent = self.current_node
        # print(f'create_new_node {node}')
        
        # if node.key:
        node.parent.add_child(node)
        self.current_node = node
        self.push(node)

        return node
    
    def display_stack(self):

        for i, node in enumerate(self.stack):
            print(f"node {i} => {node}")
            
    def run(self):
        pending_key = None
        for token in self.token_stream:
            if token.is_start_object():
                
                if self.current_node.type == NodeType.Array:
                    key = len(self.current_node.children) if self.current_node.children else 0
                else:
                    key = pending_key
                    pending_key = None
                node = self.create_new_node(NodeType.Object, key)
                # node.parent.add_child(node)
                pending_key = None

            if token.is_start_array():
                node = self.create_new_node(NodeType.Array, pending_key)
                # print(node.parent)
                node.parent.add_child(node)
                pending_key = None

            if token.is_end_object():
                node = self.pop()
                # print(node)
                # self.current_node = self.current_node.parent

            if token.is_end_array():
                
                self.pop()
                # self.current_node = self.current_node.parent

            if token.is_key():
                pending_key = to_primitive(token.content)

            if token.is_value():
                value = token.content
                parent = self.current_node

                # if it is in an array
                if parent.type is NodeType.Array:
                    # print(f'pushing child into array object {parent}->{value}')
                    # index = len(parent.children) if parent.children else 0
                    node = self.create_new_node(NodeType.Value)
                    # node.key = index
                    # node.parent = parent
                    node.add_value(value)
                    # parent.add_element(node)

                else:
                    # it is in an object
                    node = self.create_new_node(NodeType.Value, pending_key)
                    # node.parent = parent
                    node.add_value(value)
                    # parent.add_child(node)
                    pending_key = None

                node = self.pop()
                # print(node)
                # self.current_node = self.current_node.parent
        self.display_stack()
                

if __name__ == '__main__':
    engine = Engine(schema=schema_file, target=data_file)
    engine.run()
