import sys
from token_gen import token_stream, TokenType, Token
from constants import LiteralValue

schema_storage = []
WILDCARD = "*"

error_buffer = []
BATCH_SIZE = 10
log_file = 'validation_log.txt'

# recording all errors into a log file
def write_error(message, log_file, flush=False):
    error_buffer.append(message)

    if len(error_buffer) > BATCH_SIZE or flush:
        if error_buffer:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write('\n'.join(error_buffer) + '\n')
            error_buffer.clear()

TEST_FILE = 'schema.json'

# def retrieve_schema(id=-1):
#     if id == -1:
#         return ACCEPT_NODE
#     if id == -2:
#         return REJECT_NODE
#     else:
#         return schema_storage[id]
    
class SchemaNode:
    def __init__(self):
        self.id = 0
        self.schemas = {} # key -> schema data


    def __repr__(self):
        return f"SchemaNode(id={self.id}, schemas={self.schemas})"
    
class SchemaRef:
    def __init__(self, schema_id: int):
        self.schema_id = schema_id

    def follow(self):
        return schema_storage[self.schema_id]
    
    def value(self):
        return self.schema_id
    
    def __str__(self):
        return str(self.schema_id)
    
    def __repr__(self):
        return f"ref({self.schema_id})"


def new_node():
    node = SchemaNode()
    schema_storage.append(node)
    node.id = len(schema_storage) - 1
    return node.id

def to_primitive(token):
    if isinstance(token, Token):
        return token.content.strip('"')
    return token.strip('"')


ACCEPT_NODE = SchemaNode()
ACCEPT_NODE.id = -1
# ACCEPT_NODE.schemas['*'] = LiteralValue(True)
ACCEPT_NODE_ID = ACCEPT_NODE.id

REJECT_NODE = SchemaNode()
REJECT_NODE.id = -2
# REJECT_NODE.schemas['*'] = LiteralValue(False)
REJECT_NODE_ID = REJECT_NODE.id
    

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
