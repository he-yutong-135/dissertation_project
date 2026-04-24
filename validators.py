from constants import ValidationStatus, type_map
from schema_builder import SchemaNode, ACCRPT_NODE, REJECT_NODE
# from engine import Node

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

def validate(value, schema_node, validators):
    for rule, param in schema_node.constraints.items():
        func = validators.get(rule)
        if func:
            func(value, param)
        else:
            raise ValueError(f"Unknown validation rule: {rule}")
        
def validate_child(schema_node, key):
    if '*' in schema_node.constraints.keys():
        return schema_node.constraints['*']
    
    elif schema_node.constraints['type'] == 'object':
        children_ref = schema_node['properties']
        if children_ref is not None:
            child_ref = children_ref.follow().schemas[key]
            additional = schema_node['additionalProperties'] != True
            if child_ref or additional:
                return True

    elif schema_node.constraints['type'] == 'array':
        children_ref = schema_node['items']
        if children_ref is not None and validate_type(key, "integer"):
            return True
    else:
        return False



def validate_type(value, json_type):
    
    target_type = type_map.get(json_type)
    if target_type is None:
        raise ValueError(f'unsupported json type: {json_type}')
    
    # bool should not be classified as integer in json
    if json_type == "integer" and isinstance(value, bool):
        return False
    
    return isinstance(value, type)

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

validators = {
    "minimum": validate_minimum,
    "maximum": validate_maximum,
    "enum": validate_enum
}

def validate_type(value):
    pass

class ValidationEngine():
    def __init__(self, schema_storage):
        self.schema_storage = schema_storage

    def get_schema(self, schema_id):
        if 0 <= schema_id < len(self.schema_storage):
            return self.schema_storage[schema_id]
        elif schema_id ==  ACCRPT_NODE.id:
            return ACCRPT_NODE
        
        return REJECT_NODE
    
    def find_child(self, schema_id, key):
        # if is permissive schema and no key provided -> the outermost object, returns the first schema id
        # if key is provided -> inside a node with no constraints, return 
        if schema_id == ACCRPT_NODE.id:
            return 0 if key is None else ACCRPT_NODE.id
        if schema_id == REJECT_NODE.id:
            return REJECT_NODE.id
        
        parent_schema = self.get_schema(schema_id)
        # print(parent_schema)
        
        if parent_schema.schemas['type'] == "object":
            children_ref = parent_schema.schemas['properties']
            if children_ref is None and parent_schema.schemas['additionalProperties'] is "true":
                return ACCRPT_NODE.id
        else:
            return parent_schema.schemas['items'].value()
        
        if children_ref is None:
            return REJECT_NODE.id
        child_ref = children_ref.follow().schemas[key]

        if child_ref is None:
            return REJECT_NODE.id
        
        return child_ref.value()
    
    def validate_value(self, schema_id, value):
        for rule, param in self.get_schema(schema_id).constraints.items():
            func = validators.get(rule)
            if func:
                func(value, param)
            else:
                raise ValueError(f"Unknown validation rule: {rule}")
            
    def validate_complete(self, schema_id, children_states):
        parent_schema = self.get_schema(schema_id)
        required = parent_schema['required']
        states = {key: False for key in required}
        for key in states.keys:
            if not children_states[key]:
                return False
            
        return True

if __name__ == "__main__":
    pass