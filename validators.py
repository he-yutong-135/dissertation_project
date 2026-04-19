from enum import Enum, auto

class ValidationStatus(Enum):
    VALID = auto()
    INVALID = auto()


class ValidationError:
    def __init__(self, path, message, value=None, rule=None):
        self.path = path          
        self.message = message
        self.value = value
        self.rule = rule          

    def __repr__(self):
        return f"[{'.'.join(self.path)}] {self.message} (value={self.value})"
    
class ValidationResult:
    def __init__(self):
        self.status = ValidationStatus.VALID
        self.errors = []

    def add_error(self, error: ValidationError):
        self.status = ValidationStatus.INVALID
        self.errors.append(error)

def validate(value, schema):
    for rule, param in schema.constraints.items():
        func = validators.get(rule)
        if func:
            func(value, param)
        else:
            raise ValueError(f"Unknown validation rule: {rule}")

validators = {
    "minimum": validate_minimum,
    "maximum": validate_maximum,
    "enum": validate_enum,
}

def validate_minimum(value, min_val):
    if float(value) < min_val:
        return False, f"{value} < minimum {min_val}"
    return True, None


def validate_maximum(value, max_val):
    if float(value) > max_val:
        return False, f"{value} > maximum {max_val}"
    return True, None

def validate_enum(value, enum_list):
    if value not in enum_list:
        return False, f"{value} not in {enum_list}"
    return True, None