# Errors and status codes

DRF validation and permission errors use the standard response envelope. A simple error is:

```json
{"detail": "Authentication credentials were not provided."}
```

Field validation errors can instead use field names as keys, with a list of messages for each field. Error responses can include endpoint-specific details.

| Status | Meaning |
| --- | --- |
| `400 Bad Request` | Invalid input, missing required values, or failed validation. |
| `401 Unauthorized` | Credentials are missing, invalid, or expired. Authenticate or refresh the access token. |
| `403 Forbidden` | The authenticated user lacks the role, permission, or company access required. |
| `404 Not Found` | The requested resource does not exist or is not available to the current user. |
| `429 Too Many Requests` | A configured request throttle has been exceeded. |
| `500 Internal Server Error` | An unexpected server failure; report the operation and time to the API administrator. |

The Swagger schema documents the common `400`, `401`, `403`, and `404` responses for API view operations. Actual error bodies retain the endpoint's runtime format.
