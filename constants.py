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
        return f"value({self._value})"
    
class ErrorType(StrEnum):
    UNEXPECTED = auto()
    INCOMPLETE = auto()
    BAD_VALUE = auto()

class ValidationError():
    def __init__(self, error_type: ErrorType, message=None):
        self.error_type: ErrorType = error_type
        self.message = self.error_type
        if message:
            self.message = message

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return f'Error({self.error_type}: {self.message})'


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

def init_log(log_file=LOG_FILE):
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write("--- Validation Log Start ---\n") 
    error_buffer.clear()

# recording all errors into a log file
def write_error(message, log_file=LOG_FILE, flush=False):
    if message is not None:
        error_buffer.append(str(message))

    if flush or len(error_buffer) > BATCH_SIZE: 
        if error_buffer:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write('\n'.join(error_buffer) + '\n')
            error_buffer.clear()

schema_file, data_file = 'schema.json', 'data.json'