from .constants import Cursor, needs_log, ValidationState
from .error_log import ErrorType, ValidationError, ValidationResult, ValidationResNoLog
from .schema_builder import ACCEPT_NODE, REJECT_NODE, SchemaRef
from .validator_pool import keyword_types, is_type, composition_validators, composition_keywords, \
                    child_schema_keywords, keyword_groups, composition_keywords_lst, delayed_keyword_use_param, \
                    delayed_keyword_use_param 

import regex as re
from urllib.parse import urljoin
import inspect

NodeValidationRes = ValidationResult if needs_log else ValidationResNoLog


class ValidationEngine():
    def __init__(self, schema_storage, anchor_storage, id_storage):
        self.schema_storage = schema_storage
        self.anchor_storage = anchor_storage
        self.id_storage = id_storage

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
        ref = schema.schemas.get("$ref")

        if isinstance(ref, SchemaRef):
            return
        if ref is None:
            return

        target = self.resolve_ref(ref, schema.base_uri)
        # if can't find one, just accept it blindly
        if target is None:
            target = ACCEPT_NODE.id
        
        schema.schemas["$ref"] = target

    def resolve_ref(self, ref, base_uri):
        # local reference
        if ref.startswith("#"):
            fragment = ref[1:]

            # JSON pointer
            if fragment.startswith("/"):
                return self.find_pointer(None, fragment)

            # anchor
            if base_uri:
                return self.anchor_storage.get(f"{base_uri}#{fragment}")

            return self.anchor_storage.get(fragment)

        absolute = urljoin(base_uri, ref)

        if "#" not in absolute:
            return self.id_storage.get(absolute)

        resource, fragment = absolute.split("#", 1)

        if fragment.startswith("/"):
            return self.find_pointer(resource, fragment)


        return self.anchor_storage.get(f"{resource}#{fragment}")
    
    def find_pointer(self, resource, pointer):
        if resource is None:
            schema_ref = SchemaRef(0)
        else:
            schema_ref = self.anchor_storage.get(resource)

        if schema_ref is None:
            return None

        # remove leading /
        parts = pointer[1:].split("/")

        for key in parts:
            # JSON Pointer escaping
            key = key.replace("~1", "/").replace("~0", "~")
            node = self.get_schema(schema_ref.value())
            child = node.schemas.get(key)

            if child is None:
                return None

            schema_ref = child
        return schema_ref

    # the function that actually does the validation, it returns the validation results of the node against the schema of 'schema_id'
    def validate_schema(self, schema_id, value, children_state=None, my_type=None,  idx=None):
        # initiate index
        if idx is None:
            idx = Cursor()
        if schema_id == ACCEPT_NODE.id:
            return NodeValidationRes(ValidationError(ErrorType.NO_ERROR), schema_id=schema_id)
        if schema_id == REJECT_NODE.id:
            return NodeValidationRes(ValidationError(ErrorType.UNEXPECTED, {'value': value}), schema_id=schema_id)
        
        if isinstance(schema_id, bool):
            return ValidationError(schema_id, {'schema': 'determined'})
        if isinstance(schema_id, ValidationError):
            return schema_id
        
        errors = {}
        current_schema = self.get_schema(schema_id)

        all_data = {
            "value": value,
            "children_state": children_state,
            "idx": idx
        }

        # iterate through the current schema
        for key, param in current_schema.schemas.items():
            all_data["key"] = key
            all_data["param"] = param
            
            # obtain type requirements and validation function
            type_requirements, func = keyword_types.get(key)
            # schema only applies to the node that matches its type requirements
            if not is_type(my_type, type_requirements):
                continue

            if func is not None:
                sig = inspect.signature(func)
            
            # schema that requires the validation results from its child nodes
            if key in child_schema_keywords: 
                # if key == "dependentSchemas":
                #     errors[key] = {}
                #     schema_dict = param.follow().content() if isinstance(param, SchemaRef) else param # param could be a boolean
                #     print(f"dependentSchemas validation: {schema_dict}")
                #     for k, v in schema_dict.items():
                #         if isinstance(v, bool):
                #             errors[key][k] = v
                #         else:
                #             errors[key][k] = self.validate_schema(v.value(), value, children_state, idx=idx, my_type=my_type)
                #     all_data["schema_dict"] = errors[key]
                #     filtered_kwargs = {k: v for k, v in all_data.items() if k in sig.parameters}
                #     if not func(**filtered_kwargs): # # validation fails
                #         res_states = [res.state() for res in errors[key].values()]
                #         errors[key] = ValidationError(ErrorType.COMPOSITION_ERROR, {"rule": key, "states": ', '.join(res_states)})
                #     print(f"dependentSchemas validation result: {errors[key]}")

                if isinstance(param, bool):
                    if key == "contains" and len(value) == 0:
                        errors[key] = ValidationError(ErrorType.COMPOSITION_ERROR, {"rule": key, "states": 'empty array'})
                    elif key == "items" and len(value) == 0:
                        errors[key] = True
                    elif not param:
                        errors[key] = ValidationError(ErrorType.DETERMINED_ERROR, {"schema": {f'{key}: {param}'}})
                    else:
                        errors[key] = param
                else:
                    child_validation_results = children_state[idx.value()] if len(children_state) > 0 else children_state
                    if func is None:
                        errors[key] = child_validation_results 
                    else:
                        filtered_kwargs = {k: v for k, v in all_data.items() if k in sig.parameters}
                        if not func(**filtered_kwargs): # # validation fails
                            res_states = [res.state() for res in child_validation_results]
                            errors[key] = ValidationError(ErrorType.COMPOSITION_ERROR, {"rule": key, "states": ', '.join(res_states)})

                    # increase idx after validation
                    idx.increase()

            elif isinstance(param, SchemaRef) and key not in ["$defs", "dependentRequired", "dependentSchemas", "const", "contentSchema"]:
                next_schema_id = param.value()
                errors[key] = self.validate_schema(next_schema_id, value, children_state, idx=idx, my_type=my_type)

            elif isinstance(param, list) and key in composition_keywords_lst:
                errors[key] = list()
                for ref in param:
                    if isinstance(ref, bool):
                        if ref: 
                            next_schema_id = ACCEPT_NODE.id
                        else:
                            next_schema_id = REJECT_NODE.id
                    else:
                        next_schema_id = ref.value() 
                    errors[key].append(self.validate_schema(next_schema_id, value, children_state,idx=idx, my_type=my_type))
            elif isinstance(param, bool) and key in composition_keywords:
                errors[key] = param
            elif key in delayed_keyword_use_param:
                errors[key] = param
            else:
                if not func:
                    errors[key] = ValidationError(ErrorType.SCHEMA_ERROR, {'rule': f'{key}({param})'})
                else:
                    filtered_kwargs = {k: v for k, v in all_data.items() if k in sig.parameters}
                    print(filtered_kwargs)
                    if not func(**filtered_kwargs): # validation fails: not True
                        errors[key] = ValidationError(ErrorType.BAD_VALUE, {'value': value, 'rule': f'{key}({param})'})

        error = self.compress_errors(errors, schema_id)
        return error

    # some keywords cannot be validated in a streaming manner, the validation results of other keywords are needed
    # thus they are temporarily stored in a structure the resembles the schema itself. 
    def compress_errors(self, errors, schema_id):
        if isinstance(errors, NodeValidationRes) or isinstance(errors, bool): 
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
            for group in keyword_groups: 
                _, func = keyword_types.get(group)
                res, states = func(errors)
                if not res:
                    result += ValidationError(ErrorType.COMPOSITION_ERROR, {"rule": group, "states": states})

            for k, v in errors.items():
                errors[k] = self.compress_errors(v, schema_id)
            
            for k, v in errors.items():
                res_lst = v if isinstance(v, list) else [v]
                res_states = []
                for res in res_lst:
                    if bool(res): res_states.append('valid')
                    else: res_states.append('invalid')

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
                type_requirements, _ = keyword_types.get(k)

                # only record the schema that can be applied on this node
                if not is_type(parent_type, type_requirements):
                    continue

                if isinstance(v, bool):
                    continue # its result is determined, no need for validation

                if k in child_schema_keywords:
                    if k == 'properties' or k == 'patternProperties':
                        extra_schemas.append((k, v.follow().content())) # store a dict 
                    elif k == 'prefixItems':
                        schema_dict = dict(enumerate(v))
                        extra_schemas.append((k, schema_dict))
                    else:
                        extra_schemas.append((k, v))
                    
                elif k in composition_keywords:
                    v = v if isinstance(v, list) else [v]
                    for ref in v:
                        if isinstance(ref, bool):
                            continue # its result is determined, no need for validation
                        else:
                            extra_schemas += self.collect_schemas_for_children(ref, parent_type)
        return extra_schemas
    
    def collect_schemas_for_me(self, schema_lst, my_key):
        schema_ids = []
        schema_lst = schema_lst if isinstance(schema_lst, list) else [schema_lst]

        for schema_tuple in schema_lst:
            key, schema = schema_tuple
            schema_ref = None
            
            if isinstance(schema, SchemaRef): 
                self.update_schema(schema)
                schema_ids.append(schema)

            # use key to find the schema (object uses key, array uses index)
            elif isinstance(schema, dict):
                # pattern properties 
                if key == 'patternProperties':
                    matches = []
                    for k, v in schema.items():
                        if re.search(k, my_key):
                            matches.append(v)
                    if len(matches) > 0:
                        schema_ref = tuple(matches)
                else:
                    # properties or prefixItems
                    schema_ref = schema.get(my_key, None)

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
            else:
                raise Exception(f'unexpected schema lst provided: {schema_lst}')
        assert len(schema_lst) == len(schema_ids)
        return schema_ids