"""Shared, conservative OpenAPI metadata for API views without serializers."""

import re

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import serializers


from drf_spectacular.openapi import AutoSchema


class UniquePathAutoSchema(AutoSchema):
    """Preserve parameter names in IDs for otherwise identical route shapes."""

    def get_operation_id(self):
        operation_id = super().get_operation_id()
        parameter_names = re.findall(r"<(?:(?:int|str|slug|uuid|path):)?([a-zA-Z_][a-zA-Z0-9_]*)>", self.path_regex)
        if parameter_names:
            operation_id = f"{operation_id}_{'_'.join(parameter_names)}"
        return operation_id


class ErrorResponseSerializer(serializers.Serializer):
    """The common DRF error envelope used by documented operations."""

    detail = serializers.CharField(required=False)


def document_api_view(tag):
    """Attach consistent operation names, examples, and common error responses.

    Existing serializers remain authoritative: this decorator supplies a
    response shape only for APIViews that do not declare a serializer.
    """
    def decorate(view_class):
        operations = {}
        methods = ("get", "post", "put", "patch", "delete")
        label = re.sub(r"(?<!^)(?=[A-Z])", " ", view_class.__name__)
        label = re.sub(r"\b(API View|APIView|View)\b", "", label).strip()
        summary = label or view_class.__name__
        description = (view_class.__doc__ or "").strip()
        if not description:
            description = f"{summary}. Results and permissions follow the endpoint's configured behavior."
        for method in methods:
            if not hasattr(view_class, method):
                continue
            kwargs = {
                "summary": summary,
                "description": description,
                "tags": [tag],
                "responses": {
                    200: OpenApiResponse(response=dict, description="The request completed successfully."),
                    201: OpenApiResponse(response=dict, description="The resource was created."),
                    204: OpenApiResponse(description="The request completed without a response body."),
                    400: OpenApiResponse(response=ErrorResponseSerializer, description="Invalid request."),
                    401: OpenApiResponse(response=ErrorResponseSerializer, description="Authentication is required or the token is invalid."),
                    403: OpenApiResponse(response=ErrorResponseSerializer, description="The authenticated user lacks permission."),
                    404: OpenApiResponse(response=ErrorResponseSerializer, description="The requested resource was not found."),
                },
                "examples": [OpenApiExample("Error response", {"detail": "Invalid request."}, response_only=True, status_codes=[400])],
            }
            if method in ("post", "put", "patch"):
                kwargs["request"] = dict
                kwargs["examples"].append(OpenApiExample("Request", {"example": "value"}, request_only=True))
            operations[method] = extend_schema(**kwargs)
        if operations:
            return extend_schema_view(**operations)(view_class)
        return view_class
    return decorate


def document_api_function(tag, summary, description):
    """Document a function-based DRF endpoint with the same error contract."""
    return extend_schema(
        summary=summary,
        description=description,
        tags=[tag],
        responses={
            200: OpenApiResponse(response=dict, description="The request completed successfully."),
            400: OpenApiResponse(response=ErrorResponseSerializer, description="Invalid request."),
            401: OpenApiResponse(response=ErrorResponseSerializer, description="Authentication is required or the token is invalid."),
            403: OpenApiResponse(response=ErrorResponseSerializer, description="The authenticated user lacks permission."),
            404: OpenApiResponse(response=ErrorResponseSerializer, description="The requested resource was not found."),
        },
        examples=[OpenApiExample("Response", {"results": []}, response_only=True)],
    )
