from django.http import HttpResponse


class AppApiCorsMiddleware:
    """Lightweight CORS middleware for app API endpoints.

    Ensures browser preflight (OPTIONS) and normal responses include
    required CORS headers for routes under /api/app/v1/.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _is_app_api_path(path):
        return path.startswith("/api/app/v1/")

    @staticmethod
    def _apply_headers(response):
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Authorization, Content-Type, Accept, Origin"
        response["Access-Control-Max-Age"] = "86400"
        return response

    def __call__(self, request):
        if self._is_app_api_path(request.path) and request.method == "OPTIONS":
            return self._apply_headers(HttpResponse(status=204))

        response = self.get_response(request)

        if self._is_app_api_path(request.path):
            response = self._apply_headers(response)

        return response
