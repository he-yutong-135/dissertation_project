from constants import ValidationStatus, type_map, ErrorType, ValidationError
from schema_builder import ACCEPT_NODE, REJECT_NODE, SchemaRef, extra_node, print_schema_storage
import re

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

def validate_multiple_of(value, multiple):
    if float(value) % float(multiple) != 0:
        return False
    return True

def validate_exclusive_maximum(value, exclusive_max):
    if float(value) >= exclusive_max:
        return False
    return True

def validate_validate_minimum_len(value, min_len):
    if len(value) < min_len:
        return False
    return True

def validate_validate_maximum_len(value, max_len):
    if len(value) > max_len:
        return False
    return True

def validate_pattern(value, pattern):
    print(f'validating pattern: {pattern} with value: {value}')
    if not re.search(str(pattern), value):
        return False
    return True

validator_storage = {
    "minimum": validate_minimum,
    "maximum": validate_maximum,
    "enum": validate_enum,
    "type": validate_type,
    "multipleOf": validate_multiple_of,
    "exclusiveMaximum": validate_exclusive_maximum,
    "minLength": validate_validate_minimum_len,
    "maxLength": validate_validate_maximum_len,
    "pattern": validate_pattern,
    "default": lambda value, default: True, # default does not affect validation result
    "minItems": validate_minimum,
    "maxItems": validate_maximum
}

array_children_schemas = ['minItems', 'maxItems']
object_children_schemas = ['properties', 'required']

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
        if schema_id == ACCEPT_NODE.id:
            return 0 if key == 'top_object' else ACCEPT_NODE.id
        if schema_id == REJECT_NODE.id:
            return REJECT_NODE.id
        
        parent_schema = self.get_schema(schema_id)
        # print(f'parent schema: {parent_schema}')

        child_schema_id = None

        if parent_schema.schemas['type'] == "array":
            
            child_schema_id = parent_schema.schemas['items'].value()
            # print(f'array schema: key: {key} -> child schema: {child_schema_id}')
            # return child_schema_id

        elif parent_schema.schemas['type'] == "object":
            # print(f'parent schema: {parent_schema}, key: {key}')
            children_ref = parent_schema.schemas['properties']
            add_props = parent_schema.schemas.get('additionalProperties', True)
            if children_ref and key in children_ref.follow().schemas.keys():
                # print(f'find child: {schema_id}, {key} -> {children_ref.follow().schemas[key]}')
                child_ref = children_ref.follow().schemas.get(key, None)
                # print(f'find child ref: {key} -> {child_ref}')
                if child_ref:
                    # there is a schema with this key, return the id directly
                    child_schema_id =  child_ref.value()
            
            # if no corresponding schema found
            elif add_props: 
                return ACCEPT_NODE.id
            elif isinstance(add_props, SchemaRef): child_schema_id = add_props.value()
            
        if child_schema_id is None:
            # if the current node is either an object nor an array, it should not have a child node
            return REJECT_NODE.id

        if child_schema_id != REJECT_NODE.id and child_schema_id != ACCEPT_NODE.id:
            self.update_schema(child_schema_id)
        
        
        return child_schema_id
    

    def update_schema(self, schema_id):
        schema = self.get_schema(schema_id)
        # print(f'updating schema: {schema}')
        type = schema.schemas.get('type', None)
        # value node does not have complex validation rules
        if type == 'object' or type is None:
            return
        
        # if the schema is of type array, move its schema on children to the items schema
        if type == 'array':
            items_ref = schema.schemas.get('items', None)
            if items_ref:
                items_schema_id = items_ref.value()
                items_schema = self.get_schema(items_schema_id)
                for key, value in schema.schemas.items():
                    if key in array_children_schemas:
                        items_schema.schemas[key] = value
                        schema.schemas[key] = None

        schema.schemas = {k: v for k, v in schema.schemas.items() if v is not None}
    
    def validate_value(self, schema_id, value):
        errors = []
        if schema_id == -1:
            return ValidationStatus.VALID, errors
        if schema_id == -2:
            # print(f'validate_value: {value} with schema_id: {schema_id} -> REJECT_NODE')
            return ValidationStatus.INVALID, [ValidationError(ErrorType.UNEXPECTED, f'unexpected value or object: {value}')]
        
        current_schema = self.get_schema(schema_id)
        # print(f'{current_schema} with {value}')
        for key, param in current_schema.schemas.items():
            # print(f'validating {key} with {param}')
            
            func = validator_storage.get(key)
            if not func:
                errors.append(ValidationError(ErrorType.SCHEMA_ERROR, f'schema[{key}({param})] not found'))
            elif not func(value, param):
                errors.append(ValidationError(ErrorType.BAD_VALUE, f'value({value}) violates schema[{key}({param})]'))
            # else:
            #     print(ValidationError(ErrorType.SUCCESS, f'value({value}) satisfies schema[{key}({param})]'))
                
        if len([error for error in errors if error.error_type != ErrorType.SUCCESS]) > 0:
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