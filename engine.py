from schema_builder import build_schema, print_schema_storage, SchemaNode, SchemaRef, LiteralValue
from token_gen import token_stream, print_token_stream, TokenType
import configparser
from validators import ValidationStatus
from enum import Enum, auto

def read_config():
    config = configparser.ConfigParser()
    config.read('config.ini')

    schema_file = config.get('Test', 'schema_file')
    data_file = config.get('Test', 'data_file')

    return schema_file, data_file

schema_file, data_file = read_config()

schema_storage = build_schema(schema_file)
print_schema_storage(schema_storage)
ts  = token_stream(data_file)
# print_token_stream(ts)

class NodeType(Enum):
    Object = auto()
    Array = auto()
    Value = auto()


class Node:
    def __init__(self, key=None):
        self.key = key
        self.value = None # primitive only
        self.state = ValidationStatus.VALID
        self.parent = None
        self.type = NodeType.Object # OBJECT / ARRAY / VALUE
        self.children = None # dict or list

        self.schema_id = 0

    def __repr__(self):
        value = ''
        if self.value is not None:
            value = f': value({self.value})'
        elif self.children is not None:
            if self.type is NodeType.Object:
                value = f': children({list(self.children.keys())})'
            elif self.type is NodeType.Array:
                value = f': array({list(self.children.values())})'
        return f'[{self.type}| {self.key}{value}]'

    def set_schema(self, id):
        self.schema_id = id

    def set_value(self, value):
        # if self.type != "value":
        #     raise TypeError()

        self.value = value

    def add_child(self, node):
        if self.children is None:
            self.children = {}
        # if self.type != "object":
        #     raise TypeError()

        self.children[node.key] = node

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

    # def add_element(self, node):
    #     if self.children is None:
    #         self.children = {}
    #     # if self.type != "array":
    #     #     raise TypeError()
    #     # i = len(self.children)
    #     self.children[node.key] = node

current_node = None
current_schema = None

class Engine():
    def __init__(self, schema=None, target=None, validators=None):
        # self.dummy_node = Node('root')
        self.stack = [Node('root')] # adding a dummy node to eliminate the need of boundary checking
        self.schema_storage = build_schema(schema) if schema is not None else None
        self.token_stream = token_stream(target) if target is not None else None
        self.validators = validators

        self.current_node = self.stack[0]
        self.current_schema = self.schema_storage[0] # starting schema for outermost json object

    def change_schema(self, file_name):
        self.schema_storage = build_schema(file_name)
        self.current_schema = self.schema_storage[0]

    def change_target(self, file_name):
        self.token_stream = token_stream(file_name)

    def push(self, node):
        # if node.key is None:
        #     raise ValueError('when pushed, node has to have a key')
        
        # if node.key == 'root':
        #     node.schema_id = 0
        # else:
        #     # print(f'finding schema for {node}')
        
        # print(f'pushing node {node} with current_schema: {self.current_schema}')
        child_schema_id = self.current_schema.find_child_schema(node.key)
        node.schema_id = child_schema_id
        # print(f'push: {node} with schema id: {child_schema_id}')

        self.current_node = node
        self.current_schema = self.schema_storage[node.schema_id]
        self.stack.append(node)

    def pop(self):
        node = self.stack.pop()
        print(f'pop: {node} has schema {node.schema_id}')
        
        # if len(self.stack) > 0 and node.parent is None:
        if node.parent is None:
            raise ValueError('standalone node')
        
        self.verify_node(node)

        # if len(self.stack) > 0:
        #     self.current_node = node.parent
        #     self.current_schema = self.schema_storage[node.parent.schema_id]
        # else:
        self.current_node = node.parent
        self.current_schema = self.schema_storage[node.parent.schema_id]
        # self.display_stack()

        return node

    def verify_node(self, node):
        pass

    def verify_structure(self, node):
        if node.key is None:
            raise ValueError(f'key is none:')
        
        return True

    # this function takes a value and a schema, and verifies if the value obeys the schema
    def validate(self, value, schema):
        for rule, param in schema.constraints.items():
            func = self.validators.get(rule)
            if func:
                func(value, param)
            else:
                raise ValueError(f"Unknown validation rule: {rule}")
            
    def create_new_node(self, type, key=None):
        node = Node(key)
        node.type = type
        node.parent = self.current_node
        
        # if node.key is None:
        #     raise ValueError('node key has to be valid before being added to its parent node')
        if node.key:
            node.parent.add_child(node)
        self.current_node = node
        self.push(node)

        return node
    
    def display_stack(self):
        # if len(self.stack) == 0:
        #     print('stack is empty')
        #     return
        # else:
        for i, node in enumerate(self.stack):
            print(f"node {i} => {node}")
            
    def run(self):
        pending_key = None
        for token in self.token_stream:
            if token.is_start_object():
                
                # if len(self.stack) == 0:
                #     root_key = 'root' if pending_key is None else pending_key
                    
                #     node = Node(root_key)
                #     node.parent = None
                #     self.push(node)
                # else:
                if self.current_node.type == NodeType.Array:
                    key = len(self.current_node.children) if self.current_node.children else 0
                else:
                    key = pending_key
                    pending_key = None
                node = self.create_new_node(NodeType.Object, key)
                # node.parent.add_child(node)
                pending_key = None

            if token.is_start_array():
                # if len(self.stack) == 0:
                #     node = Node('root')
                #     node.type = NodeType.Array
                #     node.parent = None
                #     self.push(node)
                # else:
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
                pending_key = token.content

            if token.is_value():
                value = token.content
                parent = self.current_node

                # if it is in an array
                if parent.type is NodeType.Array:
                    
                    index = len(parent.children) if parent.children else 0
                    node = self.create_new_node(NodeType.Value, index)
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
                

if __name__ == '__main__':
    engine = Engine(schema=schema_file, target=data_file)
    engine.run()


    
