from constants import Cursor, needs_log, ValidationState, get_fingerprint_arr, get_fingerprint_obj
from error_log import ErrorType, ValidationError, ValidationResult, ValidationResNoLog
from schema_builder import ACCEPT_NODE, REJECT_NODE, SchemaRef, is_schema_ref
from validator_pool import keyword_types, is_type, composition_validators, composition_keywords, child_schema_keywords, keyword_groups

import re

NodeValidationRes = ValidationResult if needs_log else ValidationResNoLog

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
        # if not a reference provided, skip updating
        if not isinstance(schema_ref, SchemaRef):
            return
        schema = self.get_schema(schema_ref.value())

        # update $ref
        ref_path = schema.schemas.get('$ref', None)
        # if it has been updated, no need to update again
        if isinstance(ref_path, SchemaRef):
            return
        if ref_path:
            def_schema = self.find_schema(ref_path)
            schema.schemas['$ref'] = def_schema
            # print(f'updating schema: $ref -> {def_schema}')

        # update const
        const_value = schema.schemas.get('const', None)
        if const_value:
            if isinstance(const_value, list) or isinstance(const_value, SchemaRef):
                schema.schemas['const'] = self.calculate_const_value(const_value)

            print(f'update const: {schema.schemas['const']}')

    def calculate_const_value(self, const_value):
        if isinstance(const_value, list):
            const_value = [self.calculate_const_value(val) for val in const_value]
            return get_fingerprint_arr(const_value)
        elif isinstance(const_value, SchemaRef):
            const_dict = const_value.follow().content()
            const_dict = {k: self.calculate_const_value(v) for k, v in const_dict.items()}
            return get_fingerprint_obj(const_dict)
        else:
            return const_value


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
                
    def validate_schema(self, schema_id, value, children_state=None, my_type=None,  idx=None):
        if idx is None:
            idx = Cursor()
        # print(f'validate_schema: {value} with schema id: {schema_id}')
        if schema_id == ACCEPT_NODE.id:
            return NodeValidationRes(ValidationError(ErrorType.NO_ERROR), schema_id=schema_id)
        if schema_id == REJECT_NODE.id:
            return NodeValidationRes(ValidationError(ErrorType.UNEXPECTED, {'value': value}), schema_id=schema_id)
        
        if isinstance(schema_id, bool) or isinstance(schema_id, ValidationError):
            return schema_id
        
        errors = {}
        current_schema = self.get_schema(schema_id)
        print(f'validating with {current_schema}, {value}, {children_state}')
        for key, param in current_schema.schemas.items():
            
            
            # obtain type requirements and validation function
            print(f'key: {key}: {param}')
            type_requirments, func = keyword_types.get(key)
            print(f'key: {key}: {param}, key requirements: {type_requirments}, my type: {my_type}')

            # schema only applies to the node that matches its type requirements
            if not is_type(my_type, type_requirments):
                continue

            # if type matches, start 
            
            # schema that requires the validation results from its child nodes
            if key in child_schema_keywords: 
                # print(f'all states: {children_state}, state idx: {idx.value()}')
                
                # validationResult = NodeValidationRes(schema_id=schema_id)
                # it consumes one schema result
                # print(f'key: {key}: {param}')
                if isinstance(param, bool):
                    
                    if not bool(param):
                        # errors[key] = ValidationError()
                    # else:
                        errors[key] = ValidationError(ErrorType.DETERMINED_ERROR, {"schema": {f'{key}: {param}'}})
                        print(f'key: {key}: {param} -> {errors[key]}')
                    
                else:
                    child_validation_results = children_state[idx.value()] # a list
                    idx.increase()

                # res = child_schema_validators.get(key)(child_validation_results)
                # if not res:
                #     validationResult += ValidationError(ErrorType.INCOMPLETE, {'rule': key, 'schema_id': param, "value": value})

                # record the results of all children 
                # whether it is valid is determined later during compressing 
                    errors[key] = child_validation_results 

            elif key is None:
                if  not param:
                #     errors[key] = ValidationError()
                # else:
                    errors[key] = ValidationError(ErrorType.DETERMINED_ERROR, {"schema": {f'{key}: {param}'}})

            elif is_schema_ref(param) and key not in ["$defs", "dependentRequired"]:
                next_schema_id = param.value()
                errors[key] = self.validate_schema(next_schema_id, value, children_state, idx=idx)

            elif isinstance(param, list) and key in ["anyOf", "allOf", "oneOf"]:
                errors[key] = list()
                for ref in param:
                    if isinstance(ref, bool):
                        if ref: 
                            next_schema_id = ACCEPT_NODE.id
                        else:
                            next_schema_id = REJECT_NODE.id
                    else:
                        next_schema_id = ref.value() 
                    # print(f'validating {key} with value: {value} and param: {param}')
                    errors[key].append(self.validate_schema(next_schema_id, value, children_state,idx=idx, my_type=my_type))
                    # print(f'validation result for {key}: {errors[key]}')

            
            else:
                if key == 'const':
                    if isinstance(value, dict): value = get_fingerprint_obj(value)
                    if isinstance(value, list): value = get_fingerprint_arr(value)
                    print(f'const: {value}')
                if key == 'dependentRequired': 
                    param = param.follow().content()

                print(f'validating {key} with value: {value} and param: {param}')
                
                if not func:
                    errors[key] = ValidationError(ErrorType.SCHEMA_ERROR, {'rule': f'{key}({param})'})
                elif not func(value, param):
                    
                    errors[key] = ValidationError(ErrorType.BAD_VALUE, {'value': value, 'rule': f'{key}({param})'})

        # print(f'validating schema, error result {errors}')

        error = self.compress_errors(errors, schema_id)
        return error
    
    def compress_errors(self, errors, schema_id):
        print(f'compress: {errors}')
        if isinstance(errors, NodeValidationRes): 
            return errors
        
        if isinstance(errors, ValidationError):
            return NodeValidationRes(errors, schema_id=schema_id)
        
        if isinstance(errors, list):
            result_lst = []
            for item in errors:
                result_lst.append(self.compress_errors(item, schema_id))

            return result_lst
            
        result = NodeValidationRes(schema_id=schema_id)
        if isinstance(errors, dict):
            # validating dependent keywords
            # if-then-else
            for group in keyword_groups: 
                _, func = keyword_types.get(group)

                res, states = func(errors)
                if not res:
                    result += ValidationError(ErrorType.COMPOSITION_ERROR, {"rule": group, "states": states})

            for k, v in errors.items():
                # if k in ['items', 'additionalProperties']:
                #     errors[k] = ValidationError(ErrorType.NO_ERROR)
                # else:
                errors[k] = self.compress_errors(v, schema_id)

            for k, v in errors.items():
                
                # if k in ['if', 'then', 'else']: continue # they are processed
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
    
    def collect_schemas_for_children(self, schema_lst, parent_type):
        extra_schemas = []
        schema_lst = schema_lst if isinstance(schema_lst, list) else [schema_lst]

        for schema_id in schema_lst:
            
            if not isinstance(schema_id, SchemaRef):
                continue

            schema = self.get_schema(schema_id)

            for k, v in schema.content().items():
                # print(f'collect_schemas_for_my_children: {parent_type} from {schema.content()}')
                # print(f'collect_schemas_for_children: {k}')
                type_requirements, _ = keyword_types.get(k)

                # only record the schema that can be applied on this node
                if not is_type(parent_type, type_requirements):
                    continue

                if k in child_schema_keywords:
                    if isinstance(v, bool):
                        continue # its result is determined, no need for validation

                    if k == 'properties' or k == 'patternProperties':
                        extra_schemas.append((k, v.follow().content())) # store a dict 
                    elif k == 'prefixItems':
                        schema_dict = dict(enumerate(v))
                        extra_schemas.append((k, schema_dict))
                        # print(f'extra_schemas: {schema_dict}')
                    else:
                        extra_schemas.append((k, v))
                    
                elif k in composition_keywords:
                    # print(f'composition_keywords: {k}: {v}')
                    v = v if isinstance(v, list) else [v]
                    for ref in v:
                        if isinstance(ref, bool):
                            continue # its result is determined, no need for validation
                        else:
                            extra_schemas += self.collect_schemas_for_children(ref, parent_type)
                            print(f'next: {ref} -> {extra_schemas}')

        # print(f'collects: {extra_schemas} for children')
        return extra_schemas
    
    def collect_schemas_for_me(self, schema_lst, my_key, my_type):
        # if not my_key:
        #     return None
        schema_ids = []
        schema_lst = schema_lst if isinstance(schema_lst, list) else [schema_lst]
        print(f'collect_schemas_for_me from {schema_lst}, My info: {my_key}, {my_type}')

        for schema_tuple in schema_lst:
            key, schema = schema_tuple

            # if key == "properties" and (my_type is NodeType.Array or isinstance(my_key, int)):
            #         schema_ids.append(ACCEPT_NODE.id)
            # elif isinstance(schema, bool):
            #     continue # schema with bool as parameter does not need validation

            # a schema reference means a schema must be satisfied 
            schema_ref = None
            if isinstance(schema, SchemaRef): 
                self.update_schema(schema)
                schema_ids.append(schema)

            # use key to find the schema (object uses key, array uses index)
            elif isinstance(schema, dict):
                # pattern properties 
                if key == 'patternProperties':
                    matches = []
                    # print(f'collect_schemas_for_me patternProperties: {schema}, key: {my_key}')
                    print(my_key)
                    print(repr(my_key))
                    for k, v in schema.items():
                        print("pattern:", repr(k))
                        if re.search(k, my_key):
                            if isinstance(v, bool):
                                if not v:
                                    v = ValidationError(ErrorType.DETERMINED_ERROR, {"schema": {f'{key}: {schema_ref}'}})
                                else:
                                    v = False
                            matches.append(v)
                    # print(f'patternProperties matches: {matches}')
                    if len(matches) > 0:
                        schema_ref = tuple(matches)
                    print(f'patternProperties matches: {schema_ref}: {type(schema_ref)}')
                else:
                    # properties or prefixItems
                    schema_ref = schema.get(my_key, None)
                    print(f'key: {my_key}, properties: {schema_ref}')

                    # sometimes schema provides a boolean indicating if it is valid or not
                    if isinstance(schema_ref, bool):
                        if not schema_ref:
                        #    schema_ref = ValidationError()
                        # else:
                            schema_ref = ValidationError(ErrorType.DETERMINED_ERROR, {"schema": {f'{key}: {schema_ref}'}})
                        else:
                            schema_ref = False

                # if there are matches
                if schema_ref is not None:
                    if isinstance(schema_ref, SchemaRef):
                        self.update_schema(schema_ref)
                    elif isinstance(schema_ref, tuple):
                        for id in schema_ref:
                            self.update_schema(id)
                    schema_ids.append(schema_ref)
                else:
                    # no match found, use no match to indicate this result
                    schema_ids.append(ValidationState.NoMatch)

                print(f'returns {schema_ids}')
            else:

                raise Exception(f'unexpected schema lst provided: {schema_lst}')
            
        # print(f'collects: {schema_ids}')
            
        assert len(schema_lst) == len(schema_ids)
        return schema_ids