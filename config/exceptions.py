from rest_framework import status as http_status
from rest_framework.views import exception_handler as drf_exception_handler

DEFAULT_CODES = {
    http_status.HTTP_401_UNAUTHORIZED: "not_authenticated",
    http_status.HTTP_403_FORBIDDEN: "permission_denied",
    http_status.HTTP_404_NOT_FOUND: "not_found",
}


def _exception_code(exc, response):
    try:
        code = exc.get_codes()
    except Exception:
        code = None

    if isinstance(code, dict):
        return None
    if isinstance(code, str) and code and code != "error":
        return code

    return DEFAULT_CODES.get(response.status_code)


def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(response.data, dict) and "detail" in response.data:
        code = _exception_code(exc, response)
        if code:
            response.data.setdefault("code", code)

    return response
