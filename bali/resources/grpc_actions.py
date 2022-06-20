from fastapi_pagination import LimitOffsetParams, set_page
from fastapi_pagination.limit_offset import Page
from pydantic import BaseModel

from .._utils import parse_dict
from ..exceptions import ReturnTypeError
from ..paginate import paginate
from ..schemas import get_schema_in, UpdateRequest
from ..utils import MessageToDict, ParseDict


# noinspection PyProtectedMember
def process_rpc(resource, func):
    """Process rpc actions

    :param resource: Resource instance
    :param func: Resource action process function
    :return:
    """
    request_data = MessageToDict(
        resource._request,
        including_default_value_fields=True,
        preserving_proto_field_name=True,
    )

    if func.__name__ == 'get':
        pk = resource._request.id
        result = func(resource, pk)
        result = parse_dict(result, schema=resource.schema)
        response_data = {'data': result}

    elif func.__name__ == 'list':
        schema_in = get_schema_in(func, default_by_action=True)
        result = func(resource, schema_in(**request_data))
        # Paginated the result queryset or iterable object
        if isinstance(result, BaseModel):
            raise ReturnTypeError(
                'Generic actions `list` should return a sequence'
            )
        else:
            set_page(Page)
            params = LimitOffsetParams(
                limit=request_data.get('limit') or 10,
                offset=request_data.get('offset'),
            )
            response_data = paginate(
                result,
                params=params,
                is_rpc=True,
                model_schema=resource.schema,
            )

    elif func.__name__ in ['create', 'update']:
        generic_schema_in = get_schema_in(func, default_by_action=True)
        generic_schema = generic_schema_in(**request_data)

        if isinstance(generic_schema, UpdateRequest):
            result = func(
                resource,
                resource.schema(**generic_schema.data),
                pk=generic_schema.id,
            )
        else:
            result = func(resource, resource.schema(**generic_schema.data))

        result = parse_dict(result, schema=resource.schema)
        response_data = {'data': result}

    elif func.__name__ == 'delete':
        pk = resource._request.id
        result = func(resource, pk)
        response_data = {'result': bool(result)}

    else:
        # custom action
        schema_in = get_schema_in(func)
        result = func(resource, schema_in(**request_data))
        if not isinstance(result, dict):
            result = result.dict()
        response_data = result

    # Convert response data to gRPC response
    return ParseDict(
        response_data,
        resource._response_message(),
        ignore_unknown_fields=True
    )
