from constants import NodeType
from constants import Cursor, needs_log
from error_log import ErrorType, ValidationError, ValidationResult, ValidationResNoLog
from schema_builder import ACCEPT_NODE, REJECT_NODE, SchemaRef, is_schema_ref
from validator_pool import keyword_types, is_type, composition_validators, composition_keywords, child_schema_keywords, child_schema_validators

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
        schema = self.get_schema(schema_ref.value())
        ref_path = schema.schemas.get('$ref', None)
        # if it has been updated, no need to update again
        if isinstance(ref_path, SchemaRef):
            return
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
                
    def validate_schema(self, schema_id, value, children_state=None, my_type=None,  idx=None):
        if idx is None:
            idx = Cursor()
        # print(f'validate_schema: {value} with schema id: {schema_id}')
        if schema_id == ACCEPT_NODE.id:
            return NodeValidationRes(ValidationError(ErrorType.NO_ERROR), schema_id=schema_id)
        if schema_id == REJECT_NODE.id:
            return NodeValidationRes(ValidationError(ErrorType.UNEXPECTED, {'value': value}), schema_id=schema_id)
        
        errors = {}
        current_schema = self.get_schema(schema_id)
        # print(f'validating with {current_schema}')
        for key, param in current_schema.schemas.items():
            
            # obtain type requirements and validation function
            type_requirments, func = keyword_types.get(key)

            # schema only applies to the node that matches its type requirements
            if not is_type(my_type, type_requirments):
                continue

            # if type matches, start 
            
            # schema that requires the validation results from its child nodes
            if key in child_schema_keywords: 
                # print(f'all states: {children_state}, state idx: {idx.value()}')
                
                validationResult = NodeValidationRes(schema_id=schema_id)
                # it consumes one schema result
                # print(children_state)
                child_validation_results = children_state[idx.value()] # a list
                idx.increase()

                print(f'child_schema_validators: {key}')
                res = child_schema_validators.get(key)(child_validation_results)
                if not res:
                    validationResult += ValidationError(ErrorType.INCOMPLETE, {'rule': key, 'schema_id': param, "value": value})

                errors[key] = validationResult


            elif key == 'dependentRequired': 
                param = param.follow().content()

            elif is_schema_ref(param) and key != "$defs":
                next_schema_id = param.value()
                errors[key] = self.validate_schema(next_schema_id, value, children_state, idx)

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
                    errors[key].append(self.validate_schema(next_schema_id, value, children_state,idx))
                    # print(f'validation result for {key}: {errors[key]}')
            else:
                # print(f'validating {key} with value: {value} and param: {param}')
                
                if not func:
                    errors[key] = ValidationError(ErrorType.SCHEMA_ERROR, {'rule': f'{key}({param})'})
                elif not func(value, param):
                    
                    errors[key] = ValidationError(ErrorType.BAD_VALUE, {'value': value, 'rule': f'{key}({param})'})

        error = self.compress_errors(errors, schema_id)
        return error
    
    def compress_errors(self, errors, schema_id):
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
            for k, v in errors.items():
                # if k in ['items', 'additionalProperties']:
                #     errors[k] = ValidationError(ErrorType.NO_ERROR)
                # else:
                errors[k] = self.compress_errors(v, schema_id)
            if 'if' in errors.keys():
                res, states = composition_validators.get('if_then_else')(errors)
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
    
    def collect_schemas_for_children(self, schema_lst, parent_type):
        extra_schemas = []
        schema_lst = schema_lst if isinstance(schema_lst, list) else [schema_lst]

        print(f'collect_schemas_for_my_children: {parent_type} from {schema_lst}')

        for schema_id in schema_lst:
            schema = self.get_schema(schema_id)

            for k, v in schema.content().items():
                type_requirements, _ = keyword_types.get(k)

                # only record the schema that can be applied on this node
                if not is_type(parent_type, type_requirements):
                    continue

                if k in child_schema_keywords:
                    if isinstance(v, bool):
                        continue # its result is determined, no need for validation

                    if k == 'properties':
                        extra_schemas.append((k, v.follow().content())) # store a dict 
                    elif k == 'prefixItems':
                        schema_dict = dict(enumerate(v))
                        extra_schemas.append((k, schema_dict))
                        # print(f'extra_schemas: {schema_dict}')
                    else:
                        extra_schemas.append((k, v))
                    
                elif k in composition_keywords:
                    v = v if isinstance(v, list) else [v]
                    for ref in v:
                        if isinstance(ref, bool):
                            continue # its result is determined, no need for validation
                        else:
                            next_schema_id = ref.value()
                            extra_schemas += self.collect_schemas_for_children(next_schema_id)

        print(f'collects: {extra_schemas} for children')
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
            if isinstance(schema, SchemaRef): 
                self.update_schema(schema)
                schema_ids.append(schema)

            # use key to find the schema (object uses key, array uses index)
            elif isinstance(schema, dict):
                schema_ref = schema.get(my_key, None)
                if schema_ref:
                    self.update_schema(schema_ref)
                    schema_ids.append(schema_ref)
                else:
                    # no match found, considered as an error
                    schema_ids.append(REJECT_NODE.id)
            else:

                raise Exception(f'unexpected schema lst provided: {schema_lst}')
            
        print(f'collects: {schema_ids}')
            
        assert len(schema_lst) == len(schema_ids)
        return schema_ids