from token_gen import token_stream, TokenType

schema_storage = []
WILDCARD = "*"

TEST_FILE = 'schema.json'

class SchemaNode:
    def __init__(self, type=None):
        self.type = type
        self.id = 0

        # for object
        self.properties = {}   # key -> schema id
        self.required = set() # required keys
        self.additional = True

        # for array
        self.items = None     # schema id for items

        # for value
        self.constraints = {} # constraints for value 

    def validate(self, value):
        pass            
    
    def __repr__(self):
        repr = f"SchemaNode(type={self.type}"
        if self.type == "object":
            repr += f", properties={self.properties}, required={self.required}, additional={self.additional}"
        elif self.type == "array":
            repr += f", items={self.items}"
        else:
            repr += f", constraints={self.constraints}"
        repr += ")"
        return repr
    
def new_node():
    node = SchemaNode()
    schema_storage.append(node)
    node.id = len(schema_storage) - 1
    return node.id

def parse_schema(token_stream):
    schema_id = new_node()
    node = schema_storage[schema_id]

    if next(token_stream).type != TokenType.START_OBJECT:
        raise ValueError("Schema must start with an object")
    
    for token in token_stream:
        if token.type == TokenType.END_OBJECT:
            break
        if token.type != TokenType.KEY:
            raise ValueError("Expected key in schema object")
        
        parse_field(token, node, token_stream)

    return schema_id

def parse_field(token, node, token_stream):
    print(f"Parsing field {token.content} for node {node}")
    key = token.content
    
    if key == "type":
        node.type = read_value(token_stream)

    elif key == "required":
        node.required = set(parse_array_of_strings(token_stream))

    elif key == 'properties':
        node.properties = parse_properties(token_stream)

    elif key == "additionalProperties":
        node.additional = str_2_bool(read_value(token_stream))

    elif key == "items":
        node.items = parse_schema(token_stream)

    else:
        node.constraints[key] = parse_array_of_strings(token_stream)

def str_2_bool(s):
    if s.lower() == "true":
        return True
    elif s.lower() == "false":
        return False
    else:
        raise ValueError(f"Invalid boolean value: {s}")

def parse_properties(token_stream):
    props = {}
    token = next(token_stream)

    # we expect a start object token here
    if token.type != TokenType.START_OBJECT:
        raise ValueError("Expected start of properties object")
    
    for token in token_stream:
        if token.type == TokenType.END_OBJECT:
            break
        if token.type != TokenType.KEY:
            raise ValueError("Expected key in properties object")
        schema_id = parse_schema(token_stream)
        props[token.content] = schema_id
    return props

def read_value(token_stream):
    token = next(token_stream) 
    print(f"Reading value token: {token}")

    if token.type != TokenType.VALUE:
        raise ValueError("Expected value token")
    return parse_primitive(token)
    
def parse_primitive(token):
    return token.content.strip('"')

def parse_array_of_strings(token_stream):
    arr = []
    token = next(token_stream)
    print(f"Reading first token: {token}")
    if token.type == TokenType.VALUE:
        return parse_primitive(token)
    
    for token in token_stream:
        print(f"Reading array token in loop: {token}")
        if token.type == TokenType.END_ARRAY:
            break
        if token.type != TokenType.VALUE:
            raise ValueError("Expected value in array")
        arr.append(token.content.strip('"'))

    return arr

def print_schema_storage():
    for i, node in enumerate(schema_storage):
        print(f"Schema ID {i}: {node}")


def main(file_name):
    parse_schema(token_stream(file_name))
    print_schema_storage()

if __name__ == "__main__":
    main(TEST_FILE)
    
