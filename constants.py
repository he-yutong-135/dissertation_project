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
    
    def __eq__(self, value):
        return self._value == value
    
    def __str__(self):
        return str(self._value)
    
    def __bool__(self):
        if not self._value:
            return False
        return True
    
    def __hash__(self):
        return hash(self._value)
    
    def __repr__(self):
        return f"{self._value}"
    
class ErrorType(StrEnum):
    UNEXPECTED = auto()
    INCOMPLETE = auto()
    BAD_VALUE = auto()
    UNCLOSED = auto()

class ValidationError():
    def __init__(self, error_type: ErrorType, message=None):
        self.error_type: ErrorType = error_type
        self.message = None
        if message:
            self.message = message

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        if self.message:
            return f'{dent}Error: {self.message}'
        else:
            return f'{dent}Error: {self.error_type}'


type_map = {
    "string": str,
    "number": (int, float),  
    "integer": int,
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None)
}

WILDCARD = "*"

error_buffer = []
BATCH_SIZE = 10
LOG_FILE = 'validation_log.txt'
MAX_DEPTH = 10
dent = '  '

schema_file, data_file = 'schema.json', 'data.json'