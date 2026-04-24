from enum import auto, StrEnum

class NodeType(StrEnum):
    Object = auto()
    Array = auto()
    Value = auto()

    def __repr__(self):
        return self.__str__()

class SchemaType(StrEnum):
    STRUCTURE = auto()
    VALUE = auto()
    COMPILE = auto()

class ValidationStatus(StrEnum):
    VALID = auto()
    INVALID = auto()

    def __repr__(self):
        return self.__str__()

    def __bool__(self):
        return self is ValidationStatus.VALID

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