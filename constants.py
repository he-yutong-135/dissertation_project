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
    
class LiteralValue:
    def __init__(self, value):
        self._value = value
    
    def __eq__(self, other):
        if isinstance(other, LiteralValue):
            return self._value == other._value
        return self.__str__() == other
    
    def __hash__(self):
        return hash(self.__str__())
    
    def __str__(self):
        return self._value.strip('"')
    
    def __repr__(self):
        return f"value({self._value})"

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