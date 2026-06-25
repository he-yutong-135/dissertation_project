from enum import auto, StrEnum
import copy

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

    
class ErrorType(StrEnum):
    UNEXPECTED = "<UNEXPECTED>"
    INCOMPLETE = "<INCOMPLETE>"
    BAD_VALUE = "<BAD VALUE>"
    UNCLOSED = "<UNCLOSED>"
    SCHEMA_ERROR = "<SCHEMA ERROR>",
    DEPTH_ERROR = "<DEPTH ERROR>",
    COMPOSITION_ERROR = "<COMPOSITION ERROR>"
    # for test
    NO_ERROR = "<NO ERROR>"

ERROR_TEMPLATES = {
    ErrorType.UNEXPECTED: {
        "template": "unexpected: {value}",
        "keywords": ["value"]
    },
    ErrorType.BAD_VALUE: {
        "template": "value({value}) violates schema[{rule}]",
        "keywords": ["value", "rule"]
    },
    ErrorType.SCHEMA_ERROR: {
        "template": "schema[{rule}] not found",
        "keywords": ["rule"]
    },
    ErrorType.UNCLOSED: {
        "template": "unclosed structure",
        "keywords": []
    },
    ErrorType.INCOMPLETE: {
        "template": "child({value}) is not valid",
        "keywords": ["value"]
    },
    ErrorType.DEPTH_ERROR: {
        "template": "maximum allowed depth exceeded: {depth}",
        "keywords": ["depth"]
    },
    ErrorType.COMPOSITION_ERROR: {
        "template": "violates composite schema[{rule}], branch states: [{states}]",
        "keywords": ["rule", "states"]
    },
    ErrorType.NO_ERROR: {
        "template": "valid",
        "keywords": []
    }
}

class ValidationError():
    def __init__(self, error_type: ErrorType, context = None):
        # print('ValidationError created')
        self.error_type: ErrorType = error_type
        self.context = {} if context is None else context

    def __str__(self):
        return self.__repr__()
    
    def __repr__(self):
        # if no error
        # if not bool(self): return ''
        template = ERROR_TEMPLATES[self.error_type]["template"]
        return f'{self.error_type}: {template.format(**self.context)}'
    
    def __bool__(self):
        # return true if there is an error
        return self.error_type is not ErrorType.NO_ERROR
    
    def state(self):
        if self: return 'invalid'
        else: return 'valid'

    def __eq__(self, other):
        if isinstance(other, ValidationError):
            
            if self.error_type == other.error_type and self.context == other.context:
                return True
            else:
                print(f'error mismatch!: self: {repr(self.context)}, other: {repr(other.context)}')
            
        return False
    
class ValidationResult():
    def __init__(self, errors=None, node_path = None, node_info = None):
        self.errors = [] # stores a list of validation errors
        self.path = node_path
        self.info = node_info

        if isinstance(errors, ValidationError):
            self.errors.append(errors)
        elif isinstance(errors, list):
            self.errors = errors.copy()

    def add(self, other):
        if isinstance(other, list):
            for result in other:
                self.add(result) 
        elif isinstance(other, ValidationError) and other:
            self.errors.append(other)
        elif isinstance(other, ValidationResult):
            self.errors.extend([e for e in other.errors if e])
        return self
    
    def add_info(self, node_path = None, node_info = None):
        self.path = node_path
        self.info = node_info
        # print(f'create validation result: {self.errors}')
        return self
    
    def __iadd__(self, other):
        self.add(other)
        return self

    def __bool__(self):
        return any(self.errors)
    
    def __repr__(self):
        error_log = ''
        if self.path: error_log = f'invalid json item: path({self.path})\n'
        if self.info: error_log += f'{dent}node value: {self.info}\n'
        for e in self.errors:
            if e: error_log += f'{dent}{dent}{str(e)}\n'
        return error_log
    
    def __str__(self):
       return self.__repr__()
    
    def state(self):
        if self: return 'invalid'
        else: return 'valid'
    
    
def assert_single_log(validationResult, path, errors):
    errors = errors if isinstance(errors, list) else [errors]
    assert validationResult.path == path, f'path mismatch: want: {path}, get: {validationResult.path}'
    assert len(validationResult.errors) == len(errors), f'not enough errors: want {len(errors)} errors, get {len(validationResult.errors)} errors'
    for i in range(len(errors)):
        assert validationResult.errors[i] == errors[i], f'error mismatch, want: {repr(errors[i])}, get: {repr(validationResult.errors[i])}'


def assert_all_logs(logs, error_dict: dict):
    assert len(logs) == len(error_dict)
    for log in logs:
        path = log.path

        target_errors = error_dict.get(path, None)
        assert target_errors is not None, f'extra errors added: {log.path}({log.errors})'
        assert_single_log(log, path, target_errors)
    
class ValidationLog():
    def __init__(self, log_file = None):
        self._logs = []
        self.log_print = []
        self.log_file = log_file
        # start logging
        self.log_print.append('--- Validation Error Log ---\n')

    def add_log(self, errors, path=None, info=None):
        # print(f'add log to logs: {errors}')
        
        if isinstance(errors, ValidationError): errors = ValidationResult(errors)
        errors.add_info(path, info)
        self._logs.append(copy.deepcopy(errors))
        self.log_print.append(str(errors))
        # print(f'log added: {self._logs}')

    # def add_log_message(self, log):
    #     self._logs.append(log)
    #     self.log_print.append(str(log))

    def report(self, depth = 0):
        # end logging
        self.log_print.append(f'(maximum stack depth: {depth})')
        self.log_print.append('--- validation done ---')
        if self.log_file:
            with open(self.log_file, 'w') as f:
                for log in self.log_print:
                    f.write(log)
                    f.write('\n')
        return self._logs
    
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
        items.append((k, child))

    return hash(tuple(items))

def get_fingerprint_arr(children: list):
    if children is None:
        return hash(None)
    return hash(tuple(children))

WILDCARD = "*"

error_buffer = []
BATCH_SIZE = 10
LOG_FILE = 'validation_log.txt'
MAX_DEPTH = 10
dent = '  '

schema_file, data_file = 'schema.json', 'data.json'

if __name__ == "__main__":
    pass

