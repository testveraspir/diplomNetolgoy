from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


class TestErrorView(APIView):
    def get(self, request):
        try:
            raise ValueError("Это тестовая ошибка для проверки интеграции Hawk через Sentry SDK!")
        except Exception as e:
            from sentry_sdk import capture_exception
            capture_exception(e)
            return Response({"error": "Произошла внутренняя ошибка сервера",
                             "detail": str(e),
                             "code": "server_error"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
