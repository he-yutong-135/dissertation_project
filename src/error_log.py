from enum import StrEnum
from .constants import dent

class ErrorType(StrEnum):
    UNEXPECTED = "<UNEXPECTED>"
    INCOMPLETE = "<INCOMPLETE>"
    BAD_VALUE = "<BAD VALUE>"
    UNCLOSED = "<UNCLOSED>"
    SCHEMA_ERROR = "<SCHEMA ERROR>"
    DEPTH_ERROR = "<DEPTH ERROR>"
    COMPOSITION_ERROR = "<COMPOSITION ERROR>"
    DETERMINED_ERROR = "<DETERMINED ERROR>"
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
        "template": "value({value}) violates schema[{rule}], schema id: {schema_id}",
        "keywords": ["value", "rule", "schema_id"]
    },
    ErrorType.DEPTH_ERROR: {
        "template": "maximum allowed depth exceeded: {depth}",
        "keywords": ["depth"]
    },
    ErrorType.COMPOSITION_ERROR: {
        "template": "violates composite schema[{rule}], branch states: [{states}]",
        "keywords": ["rule", "states"]
    },
    ErrorType.DETERMINED_ERROR: {
        "template": "schema determined error, schema: {schema}",
        "keywords": ["schema"]
    },
    ErrorType.NO_ERROR: {
        "template": "valid",
        "keywords": []
    }
}

class ValidationResNoLog():
    def __init__(self, errors=None, node_path = None, schema_id = None):
        self.has_error = False
        if isinstance(errors, ValidationError):
            self.has_error = errors.has_error()
        elif isinstance(errors, list):
            self.has_error = any(errors)
        self.path = node_path
        self.schema_id = schema_id

    def __bool__(self):
        return not self.has_error # true means valid
    
    def has_error(self):
        return self.has_error
    
    def state(self):
        if self.has_error(): return 'invalid'
        else: return 'valid'

    def set_state(self, state):
        if state is not None: return
        self.has_error = state.has_error()

    def flip(self):
        self.has_error = not self.has_error

    def __iadd__(self, other):
        if self: return self # already an error
        if isinstance(other, list):
            for result in other:
                self.set_state(result)
        else:
            self.set_state(other)
        return self
    def __repr__(self):
        error_log = ''
        if self.schema_id: error_log += f'{dent} violates schema(id: {self.schema_id})\n'
        return error_log
    
    def __str__(self):
       return self.__repr__()
    
class ValidationError():
    def __init__(self, error_type, context = None):
        # print('ValidationError created')
        if isinstance(error_type, bool):
            if error_type:
                self.error_type = ErrorType.NO_ERROR
            else:
                self.error_type = ErrorType.DETERMINED_ERROR
        else:
            self.error_type = error_type
        self.context = {} if context is None else context

    def __str__(self):
        return self.__repr__()
    
    def __repr__(self):
        template = ERROR_TEMPLATES[self.error_type]["template"]
        return f'{self.error_type}: {template.format(**self.context)}'
    
    def __bool__(self):
        # return true if there is no error
        return self.error_type is ErrorType.NO_ERROR
    
    def has_error(self):
        return self.error_type is not ErrorType.NO_ERROR
    
    def state(self):
        if self.has_error(): return 'invalid'
        else: return 'valid'

    def __eq__(self, other):
        if isinstance(other, ValidationError):
            if self.error_type == other.error_type and self.context == other.context:
                return True
            else:
                print(f'error mismatch!: self: {repr(self.context)}, other: {repr(other.context)}')
        return False
    
class ValidationResult():
    def __init__(self, errors=None, node_path = None, schema_id = None):
        self.errors = [] # stores a list of validation errors
        self.path = node_path
        self.schema_id = schema_id

        if isinstance(errors, ValidationError):
            self.errors.append(errors)
        elif isinstance(errors, list):
            self.errors = errors.copy()

    # only add real errors
    def add(self, other):
        if isinstance(other, list):
            for result in other: 
                if result:
                    self.add(result) 
        elif isinstance(other, ValidationError) and other.has_error():
            self.errors.append(other)
        elif isinstance(other, ValidationResult) and other.has_error():
            self.errors.extend(other.errors)
        # elif isinstance(other, bool) and not other:
        #     self.errors
        return self
    
    def add_info(self, node_path = None, schema_id = None):
        if node_path:
            self.path = node_path
        if schema_id:
            self.schema_id = schema_id
        # print(f'create validation result: {self.errors}')
        return self
    
    def __iadd__(self, other):
        self.add(other)
        return self

    def __bool__(self):
        return not self.has_error() # true if it contains no error
    
    def has_error(self):
        for e in self.errors:
            if not bool(e):
                return True
        return False 
    
    def __len__(self):
        return len(self.errors)
    
    def __repr__(self):
        error_log = ''
        if self.schema_id: error_log += f'{dent}schema id: {self.schema_id}\n'
        for e in self.errors:
            error_log += f'{dent}{dent}{str(e)}\n'
        return error_log
    
    def __str__(self):
       return self.__repr__()
    
    def state(self):
        if self.has_error(): return 'invalid'
        else: return 'valid'

def format_node_info(path, info, line):
    if isinstance(line, tuple):
        if line[0] != line[1]:
            line_str = f'{line[0]} ~ {line[1]}'
        else:
            line_str = line[0]
    else:
        line_str = line
    return f'invalid json item! line: {line_str}, path: {path}, value: {info}'
    
class ValidationLog():
    def __init__(self, log_file = None):
        self._logs = []
        self.log_print = []
        self.log_file = log_file
        # start logging
        self.log_print.append('--- Validation Error Log ---\n')

    def add_log(self, errors, path=None, info=None, line=None):
        if isinstance(errors, ValidationError): errors = ValidationResult(errors)
        self.log_print.append(format_node_info(path, info, line))
        self._logs.append(errors)
        self.log_print.append(str(errors))

    def report(self, depth = 0):
        # end logging
        self.log_print.append(f'(maximum stack depth: {depth})')
        self.log_print.append('--- validation done ---')
        if self.log_file:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                for log in self.log_print:
                    f.write(log)
                    f.write('\n')
        else:
            for log in self.log_print:
                print(log)