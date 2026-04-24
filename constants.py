from enum import Enum, auto

class NodeType(Enum):
    Object = auto()
    Array = auto()
    Value = auto()

class SchemaType(Enum):
    STRUCTURE = auto()
    VALUE = auto()
    COMPILE = auto()

class ValidationStatus(Enum):
    VALID = auto()
    INVALID = auto()

type_map = {
    "string": str,
    "number": (int, float),  
    "integer": int,
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None)
}

schema_file, data_file = 'schema.json', 'data.json'