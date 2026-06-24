from constants import ValidationStatus, type_map, ErrorType, ValidationError, NodeType, ValidationResult
from schema_builder import ACCEPT_NODE, REJECT_NODE, SchemaRef, SchemaNode, is_schema_ref
import re

def validate_minimum(value, min_val):
    if not is_number(value): return True # does not apply to non-numeric value
    if float(value) < min_val:
        return False
    return True

def validate_maximum(value, max_val):
    if not is_number(value): return True # does not apply to non-numeric value
    if float(value) > max_val:
        return False
    return True

def validate_enum(value, enum_list):
    for item in enum_list:
        if value == item and type(value) == type(item):
            return True
    # if value not in enum_list:
        # return False
    return False

def is_number(value):
    # print(f'is number: {type(value)}')
    return validate_types(value, ['number', 'integer'])

def validate_type(value, schema_type):
    
    python_type = type_map.get(schema_type, None)
    if not python_type:
        return False
    
    # bool should not be classified as integer in json
    if schema_type == "integer" and isinstance(value, bool):
        return False
    
    if schema_type == "number" and isinstance(value, bool):
        return False
    
    return isinstance(value, python_type)

def validate_types(value, types):
    # if types is a list, if one type matches value, return True
    # print(f"validate_types: {value}, {types}")
    if isinstance(types, list):
        for type in types:
            # print(f"validate_type: {type}")
            if validate_type(value, type):
                return True
        # if no match found
        return False
    else:
        return validate_type(value, types)

def validate_multiple_of(value, multiple):
    if not is_number(value): return True # does not apply to non-numeric value
    # if not is_number(multiple): return False
    if float(value) % float(multiple) != 0:
        return False
    return True

def validate_exclusive_maximum(value, exclusive_max):
    if not is_number(value): return True # does not apply to non-numeric value
    # if not is_number(exclusive_max): return False
    if float(value) >= exclusive_max:
        return False
    return True

def validate_validate_minimum_len(value, min_len):
    # if not is_number(min_len): return False
    if len(value) < min_len:
        return False
    return True

def validate_validate_maximum_len(value, max_len):
    # if not is_number(max_len): return False
    if len(value) > max_len:
        return False
    return True

def validate_pattern(value, pattern):
    if not isinstance(value, str): return True # only applies to string 
    # print(f'validating pattern: {pattern} with value: {value}')
    if not re.search(str(pattern), value):
        return False
    return True

def validate_minItems(value: list, minNum):
    if not isinstance(value, list): return True # only applies to lists
    return len(value) >= minNum

def validate_maxItems(value: list, maxNum):
    if not isinstance(value, list): return True # only applies to lists
    return len(value) <= maxNum

def validate_unique_items(children, required):
    if required:
        return len(set(children)) == len(children)
    return True

def validate_dependent_required(children, dependentRequired):
    keys = children.keys() if children else []
    # print(type(dependentRequired))
    for k, v in dependentRequired.items():
        if k in keys:
            for item in v:
                if item not in keys:
                    return False
    return True

def validate_required(children, required):
    keys = children.keys() if children else []
    for item in required:
        if item not in keys:
            return False
        
    return True

def accept(value, param):
    return True

validator_storage = {
    "minimum": validate_minimum,
    "maximum": validate_maximum,
    "enum": validate_enum,
    "type": validate_types,
    "multipleOf": validate_multiple_of,
    "exclusiveMaximum": validate_exclusive_maximum,
    "minLength": validate_validate_minimum_len,
    "maxLength": validate_validate_maximum_len,
    "pattern": validate_pattern,
    "default": accept, # default does not affect validation result
    "$schema": accept,
    "$id": accept,
    "$comment": accept,
    "title": accept,
    "description": accept,
    "examples": accept,

    # array validators
    "uniqueItems": validate_unique_items,
    "minItems": validate_minItems,
    "maxItems": validate_maxItems,

    # object validators
    "dependentRequired": validate_dependent_required,
    "required": validate_required
}

ignored_keywords = ['items', 'contains', 'properties', 'additionalProperties', '$defs']

class ValidationEngine():
    def __init__(self, schema_storage):
        self.schema_storage = schema_storage

    def get_schema(self, schema_id):
        if isinstance(schema_id, SchemaRef): schema_id = schema_id.value()
        if 0 <= schema_id < len(self.schema_storage):
            return self.schema_storage[schema_id]
        elif schema_id ==  ACCEPT_NODE.id:
            return ACCEPT_NODE
        return REJECT_NODE
    
    def find_child(self, schema_id, key, parentType):
        # if is permissive schema and no key provided -> the outermost object, returns the first schema id
        # if key is provided -> inside a node with no constraints, return 
        if schema_id == ACCEPT_NODE.id:
            return 0 if key == 'top_object' else ACCEPT_NODE.id
        if schema_id == REJECT_NODE.id:
            return REJECT_NODE.id
        
        parent_schema = self.get_schema(schema_id)
        # print(f'parent schema: {parent_schema} of {parentType}')

        child_schema_id = None

        # if parent node is an array
        if parentType is NodeType.Array:
            children_ref = parent_schema.schemas.get('items', None)
            
            child_schema_id = children_ref.value() if children_ref else ACCEPT_NODE.id
            # print(f'array schema: key: {key} -> child schema: {child_schema_id}')
            # return child_schema_id

        # if parent node is an object
        elif parentType is NodeType.Object:
            # print(f'parent schema: {parent_schema}, key: {key}')
            children_ref = parent_schema.schemas.get('properties', None)
            add_props = parent_schema.schemas.get('additionalProperties', True)
            if children_ref and key in children_ref.follow().schemas.keys():
                # print(f'find child: {schema_id}, {key} -> {children_ref.follow().schemas[key]}')
                child_ref = children_ref.follow().schemas.get(key, None)
                # print(f'find child ref: {key} -> {child_ref}')
                if child_ref:
                    # there is a schema with this key, return the id directly
                    child_schema_id =  child_ref.value()
            
            # if no corresponding schema found
            elif add_props: # additionalProperties allow the addition of extra node, always accept such nodes
                return ACCEPT_NODE.id
            # if additionalProperties corresponds to a schema, bind it to all child nodes
            elif isinstance(add_props, SchemaRef): child_schema_id = add_props.value()
            
        if child_schema_id is None:
            # if the current node is either an object nor an array, it should not have a child node
            return REJECT_NODE.id

        if child_schema_id != REJECT_NODE.id and child_schema_id != ACCEPT_NODE.id:
            self.update_schema(child_schema_id)
        
        
        return child_schema_id
    
    # ref has to be parsed after all schema is parsed, thus I delay this functionality to schema binding stage
    def update_schema(self, schema_id):
        schema = self.get_schema(schema_id)
        
        ref_path = schema.schemas.get('$ref', None)
        if ref_path:
            # print(f'updating schema: {schema}')
            def_schema = self.find_schema(ref_path)
            schema.schemas['$ref'] = SchemaRef(def_schema)

    def find_schema(self, path):
        paths = path.split('/')
        paths.reverse()
        
        schema_idx = 0
        while paths:
            key = paths.pop()

            if key == '#': 
                schema_idx = 0
                continue
                 
            schema_node = self.get_schema(schema_idx)
            # print(key)
            # print(schema_node)

            next_ref = schema_node.schemas.get(key)
            if next_ref is None:
                return REJECT_NODE.id

            schema_idx = next_ref.value()
        return schema_idx
                
    def validate_schema(self, schema_id, value):
        # print(value)
        if schema_id == -1:
            return ValidationError.NO_ERROR
        if schema_id == -2:
            return ValidationError(ErrorType.UNEXPECTED, {'value': value})
        
        errors = {}
        current_schema = self.get_schema(schema_id)
        for key, param in current_schema.schemas.items():
            if key in ignored_keywords: continue
            if is_schema_ref(param):
                next_schema_id = param.value()
                errors[key] = self.validate_schema(next_schema_id, value)

            elif isinstance(param, list) and is_schema_ref(param[0]):
                errors[key] = []
                for ref in param:
                    next_schema_id = ref.value()
                    errors[key].append(next_schema_id, value)

            else:
                
                func = validator_storage.get(key)
                # if func: print(f'found validator for {key}, {param}: {value}')

                if not func:
                    
                    errors[key] = ValidationError(ErrorType.SCHEMA_ERROR, {'rule': f'{key}({param}]'})
                elif not func(value, param):
                    # print(f'validating {value}')
                    errors[key] = ValidationError(ErrorType.BAD_VALUE, {'value': value, 'rule': f'{key}({param})'})
                    # print(f'{errors[key]}')
                else:
                    errors[key] = ValidationError(ErrorType.NO_ERROR)


        error = self.compress_errors(errors)
        # if errors: print(f'after compressing: {error}')
        return error
    
    
    def compress_errors(self, errors):
        # print(f'compressing errors: {errors}')
        if isinstance(errors, ValidationResult): 
            return errors
        
        if isinstance(errors, ValidationError):
            return ValidationResult(errors)

        result = ValidationResult()
        if isinstance(errors, list):
            for item in errors:
                result += self.compress_errors(item)
            return result
            
        if isinstance(errors, dict):
            for k, v in errors.items():
                result += self.compress_errors(v)
            return result

        return result
    
    def validate_node(self, schema_id, children):
        errors = []
        if schema_id == -1:
            return ValidationStatus.VALID, errors
        if schema_id == -2:
            # print(f'validate_value: {value} with schema_id: {schema_id} -> REJECT_NODE')
            return ValidationStatus.INVALID, [ValidationError(ErrorType.UNEXPECTED, {})]
        
        current_schema = self.get_schema(schema_id)
       
        # verification
        for key, param in current_schema.schemas.items():
            while isinstance(param, SchemaRef):
                param = param.follow()

            # print(f'param: {param}')
            if isinstance(param, SchemaNode): param = param.content()
            
            func = validator_storage.get(key, None)
            # if func: print(f'found array validator for {key}, {param}: {children}')
            if not func:
                if key in ignored_keywords: continue
                errors.append(ValidationError(ErrorType.SCHEMA_ERROR, {'rule': f'{key}({param}]'}))
            elif not func(children, param):
                errors.append(ValidationError(ErrorType.BAD_VALUE, {'value': children, 'rule': f'{key}({param})'}))

        # if len([error for error in errors if error.error_type != ErrorType.SUCCESS]) > 0:
        if len(errors) > 0:
            return ValidationStatus.INVALID, errors
        
        return ValidationStatus.VALID, errors

            
    def validate_completeness(self, children_states):

        validationResult = ValidationResult()
        if children_states is None: return validationResult
        for key, value in children_states.items():
            if bool(value): # child has an error
                validationResult += ValidationError(ErrorType.INCOMPLETE, {'value': key})

        # print(f'validate_object_complete: {validationResult}')
        return validationResult
