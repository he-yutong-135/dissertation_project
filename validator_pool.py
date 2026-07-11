import re
from constants import type_map

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
    if value is None:
        return schema_type in {"object", "array", "null"}
    
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

def validate_const(value, const):
    return value == const

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
    if not isinstance(children, dict):
        return True
    keys = children.keys() if children else []
    # print(type(dependentRequired))
    
    for k, v in dependentRequired.items():
        if k in keys:
            for item in v:
                if item not in keys:
                    return False
    return True

def validate_required(children, required):
    if not isinstance(children, dict):
        return True
    # print(f'validate_required: {children}, {required}')
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
    "items": accept,
    "$defs": accept,
    "const": validate_const,

    # array validators
    "uniqueItems": validate_unique_items,
    "minItems": validate_minItems,
    "maxItems": validate_maxItems,

    # object validators
    "dependentRequired": validate_dependent_required,
    "required": validate_required
}

def validate_anyOf(res_lst: list):
    res_lst = res_lst if isinstance(res_lst, list) else [res_lst]
    for res in res_lst:
        if not res or res is None: # if one branch is valid
            return True
    return False

def validate_allOf(res_lst: list):
    res_lst = res_lst if isinstance(res_lst, list) else [res_lst]
    for res in res_lst:
        if res or  res is None: # if one branch is invalid
            return False
    return True

def validate_oneOf(res_lst: list):
    res_lst = res_lst if isinstance(res_lst, list) else [res_lst]
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

# composition handlers
composition_validators = {
    "anyOf": validate_anyOf,
    "allOf": validate_allOf,
    "oneOf": validate_oneOf,
    "not": validate_not,
    "$ref": validate_ref,
    "if_then_else": validate_if_then_else
}

composition_keywords = ["anyOf", "allOf", "oneOf", "not", "if", "then", "else", "$ref"]
composition_keywords_lst = ["anyOf", "allOf", "oneOf"]
child_schema_keywords = ["properties", "contains", "prefixItems"]

child_schema_validators = {
    "properties": validate_allOf,
    "prefixItems": validate_allOf,
    "contains": validate_anyOf
}

