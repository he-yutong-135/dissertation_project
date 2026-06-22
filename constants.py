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

    
class ErrorType(StrEnum):
    UNEXPECTED = "<UNEXPECTED>"
    INCOMPLETE = "<INCOMPLETE>"
    BAD_VALUE = "<BAD VALUE>"
    UNCLOSED = "<UNCLOSED>"
    SCHEMA_ERROR = "<SCHEMA ERROR>",
    DEPTH_ERROR = "<DEPTH ERROR>",
    # for test
    SUCCESS = "<SUCCESS>"

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
    }
}

class ValidationError():
    def __init__(self, error_type: ErrorType, context = {}):
        self.error_type: ErrorType = error_type
        # self.node_info =  node_info
        # self.path = node_path
        self.context  = context

    def __str__(self):
        return self.__repr__()
    
    def __repr__(self):
        template = ERROR_TEMPLATES[self.error_type]["template"]
        return f'{self.error_type}: {template.format(**self.context)}'
    
    def __eq__(self, other):
        if isinstance(other, ValidationError):
            if self.error_type == other.error_type and self.context == other.context:
                return True
            
        return False
    
def assert_single_log(logMessage, path, errors):
    errors = errors if isinstance(errors, list) else [errors]
    assert logMessage.path == path, f'path mismatch: want: {path}, get: {logMessage.path}'
    assert len(logMessage.errors) == len(errors), f'not enough errors: want {len(errors)} errors, get {len(logMessage.errors)} errors'
    for i in range(len(errors)):
        assert logMessage.errors[i] == errors[i], f'error mismatch, want: {errors[i]}, get: {logMessage.errors[i]}'


def assert_all_logs(logs, error_dict: dict):
    for log in logs:
        path = log.path

        target_errors = error_dict.get(path, None)
        assert target_errors is not None, f'extra errors added: {log.path}({log.errors})'
        assert_single_log(log, path, target_errors)
        
    
class LogMessage():
    def __init__(self, errors, node_path = None, node_info = None):
        self.errors = errors if isinstance(errors, list) else [errors]
        self.path = node_path
        self.info = node_info

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        log_message = ''
        if self.path: log_message = f'invalid json item: path({self.path})\n'
        if self.info: log_message += f'{dent}node info: {self.info}\n'
        for e in self.errors:
            log_message += f'{dent}{dent}{e}\n'
        # log_message += f'{dent}{dent}{self.error}\n'
        return log_message
    
class ValidationLog():
    def __init__(self, log_file = None):
        self._logs = []
        self.log_print = []
        self.log_file = log_file
        # start logging
        self.log_print.append('--- Validation Error Log ---\n')

    def add_log(self, logMessage: LogMessage):
        self._logs.append(logMessage)
        self.log_print.append(str(logMessage))

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

WILDCARD = "*"

error_buffer = []
BATCH_SIZE = 10
LOG_FILE = 'validation_log.txt'
MAX_DEPTH = 10
dent = '  '

schema_file, data_file = 'schema.json', 'data.json'

def get_fingerprint_obj(children: dict):
    if children is None:
        return hash(None)
    items = []
    for k in sorted(children.keys()):
        child = children[k] # child is guaranteed to be a primitive value
        items.append((k, child))

    return hash(tuple(items))

def get_fingerprint_arr(children: list):
    if children is None:
        return hash(None)
    return hash(tuple(children))

if __name__ == "__main__":
    pass

