import sys
from token_gen import token_stream, TokenType, Token
from enum import Enum, auto

schema_storage = []
WILDCARD = "*"

TEST_FILE = 'schema.json'

class SchemaType(Enum):
    STRUCTURE = auto()
    VALUE = auto()
    COMPILE = auto()

    
class SchemaNode:
    def __init__(self):
        self.id = 0
        self.schemas = {} # key -> schema data

    def find_child_schema(self, key):
        if key == None:
            return 0
        # print(f'find child schema for key({key}): {self.schemas['type']}')
        if self.schemas['type'] == "object":
            children_ref = self.schemas['properties']
        else:
            return self.schemas['items'].value()
        if children_ref is None:
            raise ValueError('current schema does not have child')
        # print(f'find_child_schema: {children_ref.follow().schemas.keys()}')
        child_ref = children_ref.follow().schemas[key]

        if child_ref is None:
            return None
        
        return child_ref.value()

    def validate(self, value):
        pass

    def __repr__(self):
        return f"SchemaNode(id={self.id}, schemas={self.schemas})"
    
class SchemaRef:
    def __init__(self, schema_id: int):
        self.schema_id = schema_id

    def follow(self):
        return schema_storage[self.schema_id]
    
    def value(self):
        return self.schema_id
    
    def __repr__(self):
        return f"ref({self.schema_id})"

class LiteralValue:
    def __init__(self, value):
        self.value = value

    def value(self):
        return self.value
    
    def __eq__(self, value):
        return to_primitive(self.value) == value
    
    def __repr__(self):
        return f"value({self.value})"

def new_node():
    node = SchemaNode()
    schema_storage.append(node)
    node.id = len(schema_storage) - 1
    return node.id

def to_primitive(token):
    if isinstance(token, Token):
        return token.content.strip('"')
    return token.strip('"')


PERMISSIVE_SCHMEA_NODE = SchemaNode()
PERMISSIVE_SCHMEA_NODE.id = -1
PERMISSIVE_SCHMEA_NODE.schemas['*'] = LiteralValue(True)
    

def parse_value(token_stream):
    return parse(token_stream, expected_type=TokenType.VALUE)

def parse_key(token_stream):
    return parse(token_stream, expected_type=TokenType.KEY)
    

def parse(token_stream, first_token=None, expected_type=None):
    token = first_token if first_token is not None else next(token_stream)
    # print(f"Reading first token: {token}")
    if expected_type and token.type != expected_type:
        raise ValueError(f"Expected token type {expected_type}, got {token.type}")
    
    # if this is an array, read until the end of the array and return a list of values
    if token.type == TokenType.START_ARRAY:
        return parse_array(token_stream)
    
    if token.type == TokenType.START_OBJECT:
        return parse_object(token_stream)
    
    if token.type == TokenType.VALUE:
        return LiteralValue(token.content)
    else:
        return token.content

def parse_object(token_stream):
    # create a new schema node for this schema object
    schema_id = new_node()
    node = schema_storage[schema_id]

    # parse fields in the schema object
    for token in token_stream:
        # read until the end of this schema object
        if token.type == TokenType.END_OBJECT:
            break
        if token.type != TokenType.KEY:
            raise ValueError("Expected key in schema object")
        key = to_primitive(token)
        # print(f"Parsing field: {key}")
        # store the parsed schema for this key in the current node
        node.schemas[key] = parse(token_stream)
        # print(f"Finished parsing field: {key}, value={node.schemas[key]}")
    # return a reference to this schema node
    return SchemaRef(schema_id)

def parse_array(token_stream):
    arr = []
    for token in token_stream:
        if token.type == TokenType.END_ARRAY:
            break
        arr.append(parse(token_stream, first_token=token))
    return arr


def print_schema_storage(storage=None):
    print("schema storage: ==>")
    if storage is None:
        print("Empty schema storage")
    else:
        for i, node in enumerate(storage):
            print(f"Schema ID {i}: {node}")

def build_schema(file_name):
    parse(token_stream(file_name))
    return schema_storage

if __name__ == "__main__":
    storage = None
    if len(sys.argv) > 1:
        storage = build_schema(sys.argv[1])
    else:
        storage = build_schema(TEST_FILE)
    print_schema_storage(storage)
