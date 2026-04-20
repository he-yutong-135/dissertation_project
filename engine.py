from schema_builder import build_schema, print_schema_storage
from token_gen import token_stream, print_token_stream
import configparser
from validators import ValidationStatus

def read_config():
    config = configparser.ConfigParser()
    config.read('config.ini')

    schema_file = config.get('Test', 'schema_file')
    data_file = config.get('Test', 'data_file')

    return schema_file, data_file

schema_file, data_file = read_config()

stack = []
schema_storage = build_schema(schema_file)
# print_schema_storage(schema_storage)
ts  = token_stream(data_file)
# print_token_stream(ts)

current_node = None
current_schema = None



class Node:
    def __init__(self, key):
        self.key = key
        self.value = None # this can be a list of child nodes or a single value
        self.state = ValidationStatus.VALID
        self.parent = None
        self.type = None # OBJECT / ARRAY / VALUE
        self.children = None

        self.schema_id = 0

    def set_schema(self, id):
        self.schema_id = id

    def set_value(self, value):
        self.value = value

    def add_child(self, node):
        if not isinstance(self.value, dict):
            raise TypeError("child node should belong to an object node")
        self.value[node.key] = node.state

    
