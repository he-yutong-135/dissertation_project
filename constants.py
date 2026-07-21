from enum import auto, StrEnum
from schema_builder import SchemaRef

class NodeType(StrEnum):
    Object = "object"
    Array = "array"
    String = "string"
    Number = "number"
    Integer = "integer"
    Boolean = "boolean"
    Null = "null"

    def __repr__(self):
        return self.__str__()

class SchemaType(StrEnum):
    STRUCTURE = auto()
    VALUE = auto()
    COMPILE = auto()

class ValidationState(StrEnum):
    NoMatch = 'No Match'
    def __bool__(self):
        return True # does not count as an error

class Cursor:
    def __init__(self):
        self.idx = 0

    def increase(self):
        self.idx += 1

    def value(self):
        return self.idx

type_map = {
    "string": str,
    "number": (int, float),  
    "integer": int,
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None)
}

def get_fingerprint_obj(children: dict):
    if children is None:
        return hash(None)
    items = []
    for k in sorted(children.keys()): # order does not affect equalization
        child = children[k] # child is guaranteed to be a primitive value
        items.append((k, get_fingerprint_value(child)))

    return hash(tuple(items))

def get_fingerprint_arr(children: list):
    if children is None:
        return hash(None)
    return hash(tuple([get_fingerprint_value(v) for v in children]))

def get_fingerprint_value(value):
    # bool be checked first
    if isinstance(value, bool):
        return hash(("boolean", value))

    # JSON number semantics
    if isinstance(value, (int, float)):
        return hash(("number", float(value)))
    return hash((type(value), value))

def calculate_const_value(const_value):
    if isinstance(const_value, list):
        const_value = [calculate_const_value(val) for val in const_value]
        return get_fingerprint_arr(const_value)
    elif isinstance(const_value, SchemaRef):
        const_dict = const_value.follow().content()
        const_dict = {k: calculate_const_value(v) for k, v in const_dict.items()}
        return get_fingerprint_obj(const_dict)
    elif isinstance(const_value, dict):
        const_dict = {k: calculate_const_value(v) for k, v in const_value.items()}
        return get_fingerprint_obj(const_dict)
    else:
        return const_value


WILDCARD = "*"

error_buffer = []
BATCH_SIZE = 10
LOG_FILE = 'validation_log.txt'
MAX_DEPTH = 100000000
dent = '  '

schema_file, data_file = 'schema.json', 'data.json'

if __name__ == "__main__":
    pass

needs_log = True

