from rest_framework.permissions import BasePermission
from rest_framework.exceptions import APIException
from rest_framework import status


class CustomPermissionDenied(APIException):
    def __init__(self, detail, status_code):
        self.status_code = status_code
        self.detail = detail


class IsAuthenticated(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            raise CustomPermissionDenied(
                {'Status': False, 'Error': 'Требуется авторизация.'},
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        return True


class IsShopUser(BasePermission):
    def has_permission(self, request, view):
        if request.user.type != 'shop':
            raise CustomPermissionDenied(
                {'Status': False, 'Error': 'Только для магазинов'},
                status_code=status.HTTP_403_FORBIDDEN
            )
        return True
