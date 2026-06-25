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

ignored_keywords = ['items', 'contains', 'properties', 'additionalProperties', '$defs'] # , 'if', 'then', 'else']
def validate_anyOf(res_lst: list):
    for res in res_lst:
        if not res: # if one branch is valid
            return True
        
    return False

def validate_allOf(res_lst: list):
    for res in res_lst:
        if res: # if one branch is invalid
            return False
        
    return True

def validate_oneOf(res_lst: list):
    cnt = 0
    for res in res_lst:
        if not res: cnt += 1 # count the number of valid branches
    if cnt == 1:
        return True
    else:
        return False

def validate_not(res: ValidationResult):
    if not res: # no error -> return an error
        return False # invalid
    else:
        return True # valid, pass

# composition handlers
composition_validators = {
    "anyOf": validate_anyOf,
    "allOf": validate_allOf,
    "oneOf": validate_oneOf,
    "not": validate_not,

}

def validate_if_then_else(errors: dict):
    # default to be False, which means no error
    if_value = errors.get('if', False)
    then_value = errors.get('then', False)
    else_value = errors.get('else', False)
    
    states = {'if': 'invalid' if if_value else 'valid',
               'then': 'invalid' if then_value else 'valid', 
               'else': 'invalid' if else_value else 'valid'}
    if not if_value: # if no error
        return not bool(then_value), states
    if if_value:
        return not bool(else_value), states

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

        child_schema_id = None

        # if parent node is an array
        if parentType is NodeType.Array:
            children_ref = parent_schema.schemas.get('items', None)
            
            child_schema_id = children_ref.value() if children_ref else ACCEPT_NODE.id
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
        # print(f'validate_schema: {value} with schema id: {schema_id}')
        if schema_id == -1:
            return ValidationError(ErrorType.NO_ERROR)
        if schema_id == -2:
            return ValidationError(ErrorType.UNEXPECTED, {'value': value})
        
        errors = {}
        current_schema = self.get_schema(schema_id)
        for key, param in current_schema.schemas.items():
            # print(f'validating: key :{key}, value{param}')
            if key in ignored_keywords: continue
            if key == 'dependentRequired': 
                param = param.follow().content()

            if is_schema_ref(param):
                next_schema_id = param.value()
                errors[key] = self.validate_schema(next_schema_id, value)

            elif isinstance(param, list) and is_schema_ref(param[0]):
                # print(f'a list')
                errors[key] = list()
                for ref in param:
                    # print(f'now processing schema: {ref}')
                    next_schema_id = ref.value()
                    errors[key].append(self.validate_schema(next_schema_id, value))
                    # print(errors)

            else:
                func = validator_storage.get(key)
                if not func:
                    errors[key] = ValidationError(ErrorType.SCHEMA_ERROR, {'rule': f'{key}({param}]'})
                elif not func(value, param):
                    errors[key] = ValidationError(ErrorType.BAD_VALUE, {'value': value, 'rule': f'{key}({param})'})
                else:
                    errors[key] = ValidationError(ErrorType.NO_ERROR)



        error = self.compress_errors(errors)
        # if errors: print(f'after compressing: {error}')
        return error
    
    def compress_errors(self, errors):
        # print(f'new compressing errors: {errors}')
        if isinstance(errors, ValidationResult): 
            return errors
        
        if isinstance(errors, ValidationError):
            return ValidationResult(errors)

        
        if isinstance(errors, list):
            
            result_lst = []
            for item in errors:
                result_lst.append(self.compress_errors(item))

            return result_lst
            
        result = ValidationResult()
        if isinstance(errors, dict):
            # compress the value first
            for k, v in errors.items():
                errors[k] = self.compress_errors(v)
            

            if 'if' in errors.keys():
                res, states = validate_if_then_else(errors)
                if not res:
                    # result += ValidationResult(ValidationError(ErrorType.NO_ERROR))
                # else:
                    result += ValidationResult(ValidationError(ErrorType.COMPOSITION_ERROR, {"rule": "if-then-else", "states": states}))

            
            for k, v in errors.items():
                
                if k in ['if', 'then', 'else']: continue # they are processed
                res_lst = v if isinstance(v, list) else [v]
                res_states = [res.state() for res in res_lst]
                if k in composition_validators.keys():
                    
                    res = composition_validators.get(k)(res_lst)
                    
                    if res:
                        result += ValidationResult(ValidationError(ErrorType.NO_ERROR))
                    else:
                        result += ValidationResult(ValidationError(ErrorType.COMPOSITION_ERROR, {"rule": k, "states": ', '.join(res_states)}))
                # if not of composition schema
                else:
                    result += v

            return result

        return result

    def validate_completeness(self, children_states):

        validationResult = ValidationResult()
        if children_states is None: return validationResult
        for key, value in children_states.items():
            if bool(value): # child has an error
                # print(f'add incomplete error: {key}: {value}')
                validationResult += ValidationError(ErrorType.INCOMPLETE, {'value': key})
                # print(validationResult.errors)

        # print(f'validate_object_complete: {validationResult}')
        return validationResult
