import re
from decimal import Decimal
from constants import type_map, ValidationState

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
    # print(f'validate enum: {value} and {enum_list}')
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
    # print(f'validate_type: {schema_type}')
    # if value is None:
    #     return schema_type in {"object", "array", "null"}
    
    python_type = type_map.get(schema_type, None)
    if not python_type:
        return False
    
    # bool should not be classified as integer in json
    if schema_type == "integer" and isinstance(value, bool):
        return False
    
    if schema_type == "number" and isinstance(value, bool):
        return False
    
    if schema_type == "integer" and isinstance(value, float):
        return value.is_integer()
    
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
    if not is_number(value):
        return True

    value = Decimal(str(value))
    multiple = Decimal(str(multiple))

    if multiple <= 0:
        return False

    v_exp = value.as_tuple().exponent
    m_exp = multiple.as_tuple().exponent

    scale = max(-v_exp, -m_exp)

    value_scaled = int(value * (10 ** scale))
    multiple_scaled = int(multiple * (10 ** scale))

    return value_scaled % multiple_scaled == 0

def validate_const(value, const):
    return value == const

def validate_exclusive_maximum(value, exclusive_max):
    if not is_number(value): return True # does not apply to non-numeric value
    # if not is_number(exclusive_max): return False
    if float(value) >= exclusive_max:
        return False
    return True

def validate_exclusive_minimum(value, exclusive_min):
    if not is_number(value): return True # does not apply to non-numeric value
    # if not is_number(exclusive_max): return False
    if float(value) <= exclusive_min:
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
    children = [(type(c), c) for c in children]
    # print(f'unique items: {children}')
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
    # print(f'validate_required: {children}, {required}')
    if not isinstance(children, dict):
        return True
    
    keys = children.keys() if children else []
    for item in required:
        if item not in keys:
            return False
        
    return True

def accept(value, param):
    return True

def validate_anyOf(res_lst: list):
    print(f'validate anyof: {res_lst}')
    
    res_lst = res_lst if isinstance(res_lst, list) else [res_lst]
    result = False
    for res in res_lst:
        if not res or res is None: # if one branch is valid
            result = True
            break
    return result

def validate_allOf(res_lst: list):
    # print(res_lst)
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
    print(f'validate_not: {res}')
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
    "$ref": validate_ref,
    # "if_then_else": validate_if_then_else
}

composition_keywords = ["anyOf", "allOf", "oneOf", "not", "if", "then", "else", "$ref"]
composition_keywords_lst = ["anyOf", "allOf", "oneOf"]


array_keywords = [ "contains", "prefixItems", "items"]
object_keywords = ["properties", "patternProperties", "additionalProperties", 'propertyNames']
child_schema_keywords = array_keywords + object_keywords

child_schema_validators = {
    "properties": validate_allOf,
    "prefixItems": validate_allOf,
    "contains": validate_anyOf,
    "items": validate_allOf,
    "patternProperties": validate_allOf,
    "additionalProperties": validate_allOf
}

accept_bool_param = ["enum", "const", "default", "example", "uniqueItems"] + child_schema_keywords + \
                        ["unevaluatedProperties", "anyOf", "allOf", "oneOf", "$ref"]
keyword_groups = ['if_then_else', 'property_group', 'item_group']

def validate_if_then_else(errors: dict):
    # default to be False, which means no error
    if_value = errors.pop('if', None)
    then_value = errors.pop('then', True)
    else_value = errors.pop('else', True)

    if isinstance(if_value, bool): if_value = not if_value
    if isinstance(then_value, bool): then_value = not then_value
    if isinstance(else_value, bool): else_value = not else_value
    
    # print(f'validate_if_then_else: {if_value}, {then_value}, {else_value}')
    
    states = {'if': 'invalid' if if_value else 'valid',
               'then': 'invalid' if then_value else 'valid', 
               'else': 'invalid' if else_value else 'valid'}
    
    
    if if_value is None:
        return True, states
    else:
        if not if_value: # if no error
            return not bool(then_value), states
        if if_value:
            return not bool(else_value), states
        

def validate_properties(errors):
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
        if additional:
            if isinstance(additional, list):
                i_additional = additional[i]
            else:
                i_additional = additional
        else:
            i_additional = False # default additionalProperties is true, meaning no error

        states[f'child({i})'] = {}

        properties_info = None
        if i_properties is not None:
            properties_info = 'no match'
            if i_properties is not ValidationState.NoMatch:
                
                matched = True
                if bool(i_properties):
                    properties_info = 'invalid'
                    result = False
                else:
                    properties_info = 'valid'
        if properties_info is not None:
            states[f'child({i})']['properties'] = properties_info

        pattern_info = None
        if i_patternProperties is not None:
            pattern_info = 'no match'
            if i_patternProperties is not ValidationState.NoMatch:
                matched = True
                if bool(i_patternProperties):
                    pattern_info = 'invalid'
                    result = False
                else:
                    pattern_info = 'valid'
        if pattern_info is not None:
            states[f'child({i})']['patternProperties'] = pattern_info

        additional_info = 'valid'
        if bool(i_additional): 
            additional_info = 'invalid'
        if not matched:
            if bool(i_additional): 
                result = False
                additional_info = 'invalid'

        states[f'child({i})']['additionalProperties'] = additional_info

    return result, states

def validate_items(errors):
    # print(f'validate_items: {errors}')
    prefixItems = errors.pop('prefixItems', None)
    items = errors.pop('items', None)
    cnt = 0

    # print(f'validate_items, {items}')
    if prefixItems is not None and isinstance(prefixItems, list): cnt = len(prefixItems)
    elif items is not None and isinstance(items, list): cnt = len(items)
    elif items is not None:
        return not bool(items), {'items': items.state()}
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
            i_items = False # default additionalProperties is true, meaning no error(which is represented by False)

        states[f'child({i})'] = {}

        matched = False

        prefix_info = None
        if i_prefix is not None:
            prefix_info = 'no match'
            if i_prefix is not ValidationState.NoMatch:
                matched = True
                if bool(i_prefix):
                    prefix_info = 'invalid'
                    result = False
                else:
                    prefix_info = 'valid'

        items_info = None
        # print(f'items: {i_items}, {matched}')
        if i_items is not None and not matched:
            if bool(i_items):
                items_info = 'invalid'
                result = False
            else:
                items_info = 'valid'

        if prefix_info is not None: 
            states[f'child({i})']['prefixItems'] = prefix_info
        if items is not None:
            states[f'child({i})']['items'] = items_info

    # print(f'validate_items: {states}')
    # print(f'validate_items result: {result}')

    return result, states

# def validate_propertyNames()

# key -> (type requirements, validation strategy)
keyword_types = {
    None: (None, accept),
    "$ref": (None, accept),
    "$defs": (None, accept),
    "$id": (None, accept),
    "$schema": (None, accept),
    "$anchor": (None, accept),
    # "$dynamicRef": (None, accept),
    # "$dynamicAnchor": (None, accept),
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
    "item_group": ("array", validate_items), # added
    "items": ("array", None),
    "prefixItems": ("array", None),
    "contains": ("array", validate_anyOf),
    "minItems": ("array", validate_minItems),
    "maxItems": ("array", validate_maxItems),
    "uniqueItems": ("array", validate_unique_items),

    # Object
    "property_group": ("object", validate_properties), # added
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