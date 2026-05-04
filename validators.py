from constants import ValidationStatus, type_map, ErrorType, ValidationError
from schema_builder import ACCEPT_NODE, REJECT_NODE, SchemaRef

def validate(value, schema_node, validator_storage):
    for rule, param in schema_node.constraints.items():
        func = validator_storage.get(rule)
        if func:
            func(value, param)
        else:
            raise ValueError(f"Unknown validation rule: {rule}")

def validate_minimum(value, min_val):
    if float(value) < min_val:
        return False
    return True

def validate_maximum(value, max_val):
    if float(value) > max_val:
        return False
    return True

def validate_enum(value, enum_list):
    if value not in enum_list:
        return False
    return True

def validate_type(value, type):
    if type == "object" or type == "array":
        raise TypeError('validate_type only applies to value node')
    python_type = type_map.get(type, None)
    if not python_type:
        return False
    
    # bool should not be classified as integer in json
    if type == "integer" and isinstance(value, bool):
        return False
    
    return isinstance(value, python_type)

validator_storage = {
    "minimum": validate_minimum,
    "maximum": validate_maximum,
    "enum": validate_enum,
    "type": validate_type
}

class ValidationEngine():
    def __init__(self, schema_storage):
        self.schema_storage = schema_storage

    def get_schema(self, schema_id):
        if 0 <= schema_id < len(self.schema_storage):
            return self.schema_storage[schema_id]
        elif schema_id ==  ACCEPT_NODE.id:
            return ACCEPT_NODE
        return REJECT_NODE
    
    def find_child(self, schema_id, key):
        # if is permissive schema and no key provided -> the outermost object, returns the first schema id
        # if key is provided -> inside a node with no constraints, return 
        # print(f'find child: {schema_id}, {key}')
        if schema_id == ACCEPT_NODE.id:
            return 0 if key == 'top_object' else ACCEPT_NODE.id
        if schema_id == REJECT_NODE.id:
            return REJECT_NODE.id
        
        parent_schema = self.get_schema(schema_id)

        if parent_schema.schemas['type'] == "array":
            return parent_schema.schemas['items'].value()

        if parent_schema.schemas['type'] == "object":
            children_ref = parent_schema.schemas['properties']
            add_props = parent_schema.schemas.get('additionalProperties', True)
            if children_ref and key in children_ref.follow().schemas.keys():
                child_ref = children_ref.follow().schemas.get(key, None)
                if child_ref:
                    # there is a schema with this key, return the id directly
                    return child_ref.value()
            
            # if no corresponding schema found
            if add_props: 
                return ACCEPT_NODE.id
            if isinstance(add_props, SchemaRef): return add_props.value()
            
        else:
            # if the current node is either an object nor an array, it cannot have a child node
            return REJECT_NODE.id
        
        return REJECT_NODE.id
    
    def validate_value(self, schema_id, value):
        errors = []
        if schema_id == -1:
            return ValidationStatus.VALID, errors
        if schema_id == -2:
            return ValidationStatus.INVALID, [ValidationError(ErrorType.UNEXPECTED, f'unexpected value or object: {value}')]
        
        current_schema = self.get_schema(schema_id)
        # print(f'{current_schema} with {value}')
        for key, param in current_schema.schemas.items():
            
            func = validator_storage.get(key)
            if not func or not func(value, param):
                errors.append(ValidationError(ErrorType.BAD_VALUE, f'value({value}) violates schema[{key}({param})]'))
                
        if len(errors) > 0:
            return ValidationStatus.INVALID, errors
        
        return ValidationStatus.VALID, errors
            
    def validate_object_complete(self, schema_id, children_states):
        errors = []
            
        parent_schema = self.get_schema(schema_id)
        required = parent_schema.schemas.get('required', None)
        
        for key, value in children_states.items():
            if not value:
                errors.append(ValidationError(ErrorType.INCOMPLETE, f'child({key}) is not valid'))
        if len(errors) > 0:   
            return ValidationStatus.INVALID, errors

        if not required:
            return ValidationStatus.VALID, errors
        
        for key in required:
            if key not in children_states.keys():
                errors.append(ValidationError(ErrorType.INCOMPLETE, f'child({key}) is required but does not exist'))
                
        if len(errors) > 0:    
            return ValidationStatus.INVALID, errors
            
        return ValidationStatus.VALID, errors
    
    def validate_array_complete(self, schema_id, children_states):
        errors = []
        for key, state in children_states.items():
            if not state:
                errors.append(ValidationError(ErrorType.INCOMPLETE, f'value {key} not valid'))

        if len(errors) > 0:   
            return ValidationStatus.INVALID, errors
        return ValidationStatus.VALID, errors

if __name__ == "__main__":
    pass