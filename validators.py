from constants import type_map, Cursor, needs_log
from error_log import ErrorType, ValidationError, ValidationResult, ValidationResNoLog
from schema_builder import ACCEPT_NODE, REJECT_NODE, SchemaRef, is_schema_ref
import re

NodeValidationRes = ValidationResult if needs_log else ValidationResNoLog

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
    if value is None and schema_type == 'object': return True
    
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
    # only apply to string
    if not isinstance(value, str): return False
    if len(value) < min_len:
        return False
    return True

def validate_validate_maximum_len(value, max_len):
    # only apply to string
    if not isinstance(value, str): return False
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
    "additionalProperties": accept,
    "$defs": accept,

    # array validators
    "uniqueItems": validate_unique_items,
    "minItems": validate_minItems,
    "maxItems": validate_maxItems,

    # object validators
    "dependentRequired": validate_dependent_required,
    "required": validate_required
}

def validate_anyOf(res_lst: list):
    for res in res_lst:
        if not res or res is None: # if one branch is valid
            return True
    return False

def validate_allOf(res_lst: list):
    for res in res_lst:
        if res or  res is None: # if one branch is invalid
            return False
    return True

def validate_oneOf(res_lst: list):
    cnt = 0
    for res in res_lst:
        if not res or res is None: cnt += 1 # count the number of valid branches
    if cnt == 1:
        return True
    else:
        return False

def validate_not(res):
    if not res or  res is None: # no error -> return an error
        return False # invalid
    else:
        return True # valid, pass
    
def validate_ref(res):
    if not res or  res is None: # no error
        return True # valid
    else:
        return False # invalid

# composition handlers
composition_validators = {
    "anyOf": validate_anyOf,
    "allOf": validate_allOf,
    "oneOf": validate_oneOf,
    "not": validate_not,
    "$ref": validate_ref
}

composition_keywords = ["anyOf", "allOf", "oneOf", "not", "if", "then", "else", "$ref"]
child_schema_keywords = ["properties", "items", "contains"]

child_schema_validators = {
    "properties": validate_allOf,
    "items": validate_allOf,
    "contains": validate_anyOf
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
    
    # ref has to be parsed after all schema is parsed, thus I delay this functionality to schema binding stage
    def update_schema(self, schema_ref):
        schema = self.get_schema(schema_ref.value())
        ref_path = schema.schemas.get('$ref', None)
        if ref_path:
            def_schema = self.find_schema(ref_path)
            schema.schemas['$ref'] = def_schema
            # print(f'updating schema: $ref -> {def_schema}')

    def find_schema(self, path):
        paths = path.split('/')
        paths.reverse()
        
        schema_idx = 0
        while paths:
            key = paths.pop()

            if key == '#': 
                schema_idx = SchemaRef(0)
                continue
                 
            schema_node = self.get_schema(schema_idx)
            # print(key)
            # print(schema_node)

            next_ref = schema_node.schemas.get(key)
            if next_ref is None:
                return REJECT_NODE.id

            schema_idx = next_ref
        return schema_idx
                
    def validate_schema(self, schema_id, value, children_state=None, idx=None):
        if idx is None:
            idx = Cursor()
        # print(f'validate_schema: {value} with schema id: {schema_id}')
        if schema_id == ACCEPT_NODE.id:
            return ValidationResult(ValidationError(ErrorType.NO_ERROR), schema_id=schema_id)
        if schema_id == REJECT_NODE.id:
            return ValidationResult(ValidationError(ErrorType.UNEXPECTED, {'value': value}), schema_id=schema_id)
        
        errors = {}
        current_schema = self.get_schema(schema_id)
        # print(f'validating with {current_schema}')
        for key, param in current_schema.schemas.items():
            
            if key in child_schema_keywords: 
                # print(f'all states: {children_state}, state idx: {idx.value()}')
                
                validationResult = ValidationResult(schema_id=schema_id)
                # it consumes one schema result
                child_validation_results = children_state[idx.value()] # a list
                idx.increase()

                res = child_schema_validators.get(key)(child_validation_results)
                if not res:
                    validationResult += ValidationError(ErrorType.INCOMPLETE, {'rule': key, 'schema_id': param, "value": value})

                errors[key] = validationResult

            elif key == 'dependentRequired': 
                param = param.follow().content()

            elif is_schema_ref(param) and key != "$defs":
                next_schema_id = param.value()
                errors[key] = self.validate_schema(next_schema_id, value, children_state, idx)

            elif isinstance(param, list) and is_schema_ref(param[0]):
                errors[key] = list()
                for ref in param:
                    next_schema_id = ref.value()
                    errors[key].append(self.validate_schema(next_schema_id, value, children_state,idx))
            else:
                func = validator_storage.get(key)
                if not func:
                    errors[key] = ValidationError(ErrorType.SCHEMA_ERROR, {'rule': f'{key}({param}]'})
                elif not func(value, param):
                    
                    errors[key] = ValidationError(ErrorType.BAD_VALUE, {'value': value, 'rule': f'{key}({param})'})

        error = self.compress_errors(errors, schema_id)
        return error
    
    def compress_errors(self, errors, schema_id):
        if isinstance(errors, ValidationResult): 
            return errors
        
        if isinstance(errors, ValidationError):
            return ValidationResult(errors, schema_id=schema_id)
        
        if isinstance(errors, list):
            result_lst = []
            for item in errors:
                result_lst.append(self.compress_errors(item, schema_id))

            return result_lst
            
        result = ValidationResult(schema_id=schema_id)
        if isinstance(errors, dict):
            for k, v in errors.items():
                errors[k] = self.compress_errors(v, schema_id)
            if 'if' in errors.keys():
                res, states = validate_if_then_else(errors)
                if not res:
                    result += ValidationError(ErrorType.COMPOSITION_ERROR, {"rule": "if-then-else", "states": states})
            
            for k, v in errors.items():
                
                if k in ['if', 'then', 'else']: continue # they are processed
                res_lst = v if isinstance(v, list) else [v]
                res_states = [res.state() for res in res_lst]
                
                if k in composition_validators.keys():
                    res = composition_validators.get(k)(v)
                    if not res:
                        result += ValidationError(ErrorType.COMPOSITION_ERROR, {"rule": k, "states": ', '.join(res_states)})
                else:
                    result += v

            return result

        return result
    
    def collect_schemas_for_children(self, schema_lst):
        extra_schemas = []
        schema_lst = schema_lst if isinstance(schema_lst, list) else [schema_lst]

        for schema_id in schema_lst:
            schema = self.get_schema(schema_id)

            for k, v in schema.content().items():
                if k in child_schema_keywords:
                    if k == 'properties':
                        extra_schemas.append(v.follow().content()) # store a dict 
                        additional = schema.content().get('additionalProperties', True)
                        if isinstance(additional, bool):
                            if additional: 
                                add_ref = ACCEPT_NODE.id
                            else:
                                add_ref = REJECT_NODE.id
                        else: add_ref = additional

                        v.follow().content()[None] = add_ref
                    else:
                        extra_schemas.append(v)
                    
                elif k in composition_keywords:
                    v = v if isinstance(v, list) else [v]
                    for ref in v:
                        next_schema_id = ref.value()
                        extra_schemas += self.collect_schemas_for_children(next_schema_id)
        return extra_schemas
    
    def collect_schemas_for_me(self, schema_lst, my_key):
        schema_ids = []
        schema_lst = schema_lst if isinstance(schema_lst, list) else [schema_lst]

        for schema in schema_lst:
            if isinstance(schema, SchemaRef): 
                self.update_schema(schema)
                schema_ids.append(schema)
            elif isinstance(schema, dict):
                
                schema_ref = schema.get(my_key, None)
                if schema_ref:
                    self.update_schema(schema_ref)
                    schema_ids.append(schema_ref)
                else:
                    schema_ids.append(schema.get(None, REJECT_NODE.id))
            else:
                raise Exception(f'unexpected schema lst provided: {schema_lst}')
            
        assert len(schema_lst) == len(schema_ids)
        return schema_ids