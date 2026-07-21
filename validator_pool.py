import re
from decimal import Decimal
from constants import type_map, ValidationState
from constants import get_fingerprint_arr, get_fingerprint_obj, calculate_const_value


def validate_minimum(value, param):
    if isinstance(param, bool): return param
    if float(value) < param:
        return False
    return True

def validate_maximum(value, param):
    if isinstance(param, bool): return param
    if float(value) > param:
        return False
    return True

def validate_enum(value, param):
    print(f'validate_enum: value: {value}, param: {param}')
    for item in param:
        item_val = calculate_const_value(item)
        value_val = calculate_const_value(value)
        print(f'cal: {item_val} =? {value_val}')
        if item_val == value_val:
        # if value == item and type(value) == type(item):
            return True
    return False

def is_number(value):
    return validate_types(value, ['number', 'integer'])

def validate_type(value, param):
    python_type = type_map.get(param, None)
    if not python_type:
        return False
    
    # bool should not be classified as integer in json
    if param == "integer" and isinstance(value, bool):
        return False
    
    if param == "number" and isinstance(value, bool):
        return False
    
    if param == "integer" and isinstance(value, float):
        return value.is_integer()
    
    return isinstance(value, python_type)

def validate_types(value, param):
    # if types is a list, if one type matches value, return True
    if isinstance(param, list):
        for type in param:
            if validate_type(value, type):
                return True
        # if no match found
        return False
    else:
        return validate_type(value, param)

def validate_multiple_of(value, param):
    if isinstance(param, bool): return param
    value = Decimal(str(value))
    param = Decimal(str(param))

    if param <= 0:
        return False

    v_exp = value.as_tuple().exponent
    m_exp = param.as_tuple().exponent

    scale = max(-v_exp, -m_exp)

    value_scaled = int(value * (10 ** scale))
    multiple_scaled = int(param * (10 ** scale))

    return value_scaled % multiple_scaled == 0

def validate_const(value, param):
    if isinstance(value, dict): value = get_fingerprint_obj(value)
    if isinstance(value, list): value = get_fingerprint_arr(value)
    return value == param

def validate_exclusive_maximum(value, param):
    if isinstance(param, bool): return param
    if float(value) >= param:
        return False
    return True

def validate_exclusive_minimum(value, param):
    if isinstance(param, bool): return param
    if float(value) <= param:
        return False
    return True

def validate_validate_minimum_len(value, param):
    if isinstance(param, bool): return param
    if len(value) < param:
        return False
    return True

def validate_validate_maximum_len(value, param):
    if isinstance(param, bool): return param
    if len(value) > param:
        return False
    return True

def validate_pattern(value, param):
    if isinstance(param, bool): return param
    if not re.search(str(param), value):
        return False
    return True

def validate_minItems(value: list, param):
    if isinstance(param, bool): return param
    return len(value) >= param

def validate_maxItems(value: list, param):
    if isinstance(param, bool): return param
    return len(value) <= param

def validate_unique_items(value, param):
    children = [(type(c), c) for c in value]
    if param:
        return len(set(children)) == len(children)
    return True

def validate_dependent_required(value, param):
    if isinstance(param, bool): return param
    
    param = param.follow().content()
    keys = value.keys() if value else []
    for k, v in param.items():
        if k in keys:
            for item in v:
                if item not in keys:
                    return False
    return True

def validate_required(value, param):
    if isinstance(param, bool): return param
    keys = value.keys() if value else []
    for item in param:
        if item not in keys:
            return False
    return True

def accept():
    return True

def validate_none(param):
    return param

def validate_contains(value, param, children_state, idx):
    if len(value) == 0 and isinstance(param, bool):
        return False
    errors = children_state[idx.value()] if len(children_state) > 0 else children_state
    res_lst = errors if isinstance(errors, list) else [errors]
    result = False
    for res in res_lst:
        if bool(res) or res is None: # if one branch is valid
            result = True
            break
    return result

# composition_validators
def validate_anyOf(errors):
    res_lst = errors if isinstance(errors, list) else [errors]
    result = False
    for res in res_lst:
        if bool(res) or res is None: # if one branch is valid
            result = True
            break
    return result

def validate_allOf(errors):
    res_lst = errors if isinstance(errors, list) else [errors]
    for res in res_lst:
        if not bool(res) or  res is None: # if one branch is invalid
            return False
    return True

def validate_oneOf(errors):
    cnt = 0
    for res in errors:
        if bool(res) or res is None: cnt += 1 # count the number of valid branches
    if cnt == 1:
        return True
    else:
        return False

def validate_not(errors):
    res = errors
    if bool(res) or res is None: # no error -> return an error
        return False # invalid
    else:
        return True # valid, pass
    
def validate_ref(errors):
    res = errors
    if bool(res) or  res is None: # no error
        return True # valid
    else:
        return False # invalid
# composition handlers
composition_validators = {
    "anyOf": validate_anyOf,
    "allOf": validate_allOf,
    "oneOf": validate_oneOf,
    "not": validate_not,
    "$ref": validate_ref,
    # "if_then_else": validate_if_then_else
}
composition_keywords = ["anyOf", "allOf", "oneOf", "not", "if", "then", "else", "$ref"]
composition_keywords_lst = ["anyOf", "allOf", "oneOf"]

array_keywords = [ "contains", "prefixItems", "items"]
object_keywords = ["properties", "patternProperties", "additionalProperties", 'propertyNames']
child_schema_keywords = array_keywords + object_keywords

keyword_groups = ['if_then_else', 'property_group', 'item_group']


# keyword_groups
def validate_if_then_else(errors: dict):
    # default to be False, which means no error
    if_value = errors.pop('if', None)
    then_value = errors.pop('then', True)
    else_value = errors.pop('else', True)

    # if isinstance(if_value, bool): if_value = not if_value
    # if isinstance(then_value, bool): then_value = not then_value
    # if isinstance(else_value, bool): else_value = not else_value
    
    states = {'if': 'valid' if if_value else 'invalid',
               'then': 'valid' if then_value else 'invalid', 
               'else': 'valid' if else_value else 'invalid'}
    
    
    if if_value is None:
        return True, states
    else:
        if bool(if_value): # if no error
            return bool(then_value), states
        else:
            return bool(else_value), states
        

def validate_property_group(errors):
    # print(f'validate_properties: {errors}')
    cnt = 0
    properties = errors.pop('properties', None)
    patternProperties = errors.pop('patternProperties', None)
    additional = errors.pop('additionalProperties', None)
    # print(f'validate_properties additional: {additional}')

    if properties is not None and isinstance(properties, list): cnt = len(properties)
    elif patternProperties is not None and isinstance(patternProperties, list): cnt = len(patternProperties)
    elif additional is not None and isinstance(additional, list): cnt = len(additional)
    else:
        return True, {}

    states = {}
    result = True

    # iterate through all children one by one
    for i in range(cnt):
        matched = False
        i_properties = properties[i] if properties else None
        i_patternProperties = patternProperties[i] if patternProperties else None
        if additional is not None:
            if isinstance(additional, list):
                i_additional = additional[i]
            else:
                i_additional = additional
        else:
            i_additional = True # default additionalProperties is true, meaning no error

        states[f'child({i})'] = {}

        properties_info = None
        if i_properties is not None:
            properties_info = 'no match'
            if i_properties is not ValidationState.NoMatch:
                
                matched = True
                if bool(i_properties):
                    properties_info = 'valid'
                else:
                    properties_info = 'invalid'
                    result = False
        if properties_info is not None:
            states[f'child({i})']['properties'] = properties_info

        pattern_info = None
        if i_patternProperties is not None:
            pattern_info = 'no match'
            if i_patternProperties is not ValidationState.NoMatch:
                matched = True
                if bool(i_patternProperties):
                    pattern_info = 'valid'
                    
                else:
                    pattern_info = 'invalid'
                    result = False
        if pattern_info is not None:
            states[f'child({i})']['patternProperties'] = pattern_info

        additional_info = 'valid'
        if bool(i_additional): 
            additional_info = 'valid'
        if not matched:
            if not bool(i_additional): 
                result = False
                additional_info = 'invalid'

        states[f'child({i})']['additionalProperties'] = additional_info

    return result, states

def validate_items_group(errors):
    prefixItems = errors.pop('prefixItems', None)
    items = errors.pop('items', None)
    cnt = 0

    # print(f'validate_items, {items}')
    if prefixItems is not None and isinstance(prefixItems, list): cnt = len(prefixItems)
    elif items is not None and isinstance(items, list): cnt = len(items)
    elif items is not None:
        return bool(items), {'items': items.state()}
    else: return True, {}
    result = True
    states = {}

    for i in range(cnt):
        i_prefix = prefixItems[i] if prefixItems else None
        if items is not None:
            if isinstance(items, list):
                i_items = items[i]
            else:
                i_items = items
        else:
            i_items = True # default additionalProperties is true, meaning no error(which is represented by False)

        states[f'child({i})'] = {}

        matched = False

        prefix_info = None
        if i_prefix is not None:
            prefix_info = 'no match'
            if i_prefix is not ValidationState.NoMatch:
                matched = True
                if not bool(i_prefix):
                    prefix_info = 'invalid'
                    result = False
                else:
                    prefix_info = 'valid'

        items_info = None
        # print(f'items: {i_items}, {matched}')
        if i_items is not None and not matched:
            if not bool(i_items):
                items_info = 'invalid'
                result = False
            else:
                items_info = 'valid'

        if prefix_info is not None: 
            states[f'child({i})']['prefixItems'] = prefix_info
        if items is not None:
            states[f'child({i})']['items'] = items_info

    return result, states



# key -> (type requirements, validation strategy)
keyword_types = {
    None: (None, validate_none),
    "$ref": (None, accept),
    "$defs": (None, accept),
    "$id": (None, accept),
    "$schema": (None, accept),
    "$anchor": (None, accept),
    "$comment": (None, accept),
    "title": (None, accept),
    "description": (None, accept),
    "default": (None, accept),
    "examples": (None, accept),

    # Generic validation
    "type": (None, validate_types),
    "const": (None, validate_const),
    "enum": (None, validate_enum),

    # Numeric
    "minimum": ("number", validate_minimum),
    "maximum": ("number", validate_maximum),
    "exclusiveMinimum": ("number", validate_exclusive_minimum),
    "exclusiveMaximum": ("number", validate_exclusive_maximum),
    "multipleOf": ("number", validate_multiple_of),

    # String
    "minLength": ("string", validate_validate_minimum_len),
    "maxLength": ("string", validate_validate_maximum_len),
    "pattern": ("string", validate_pattern),

    # Array
    "item_group": ("array", validate_items_group), # added
    "items": ("array", None), # validate_items),
    "prefixItems": ("array", None),
    "contains": ("array", validate_contains),
    "minItems": ("array", validate_minItems),
    "maxItems": ("array", validate_maxItems),
    "uniqueItems": ("array", validate_unique_items),

    # Object
    "property_group": ("object", validate_property_group), # added
    "properties": ("object", None),
    "patternProperties": ("object", None),
    "additionalProperties": ("object", None),
    "required": ("object", validate_required),
    "dependentRequired": ("object", validate_dependent_required),

    # Composition
    "allOf": (None, validate_allOf),
    "anyOf": (None, validate_anyOf),
    "oneOf": (None, validate_oneOf),
    "not": (None, validate_not),
    'if_then_else': (None, validate_if_then_else), # added
    "if": (None, validate_if_then_else),
    "then": (None, None),
    "else": (None, None),

    # Not implemented
    "unevaluatedProperties": (None, accept),
    "unevaluatedItems": (None, accept),
    "dynamicRef": (None, accept),
    "maxContains": (None, accept),
    "minContains": (None, accept),
    "dependentSchemas": (None, accept),
    "refRemote": (None, accept),
    "format": ("string", accept),
    "propertyNames": (None, accept),
    "dependentSchemas": (None, accept),
}

def is_type(my_type, expect_type):
    # if my_type is None:
    #     raise ValueError('Every node should have a type!')
    if expect_type is None:
        return True # meaning no type requirements, applying to all types
    if expect_type == "number":
        return my_type in ["number", "integer"]
    else:
        return my_type == expect_type