from rest_framework.request import Request
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db.models import Q
from django.http import JsonResponse
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView
from backend.models import Contact, ConfirmEmailToken
from backend.serializers import UserSerializer, ContactSerializer
from backend.signals import new_user_registered, new_order


class RegisterAccount(APIView):
    """Класс для обработки запросов на регистрацию пользователей-покупателей."""

    def post(self, request, *args, **kwargs):
        """Обрабатывает запрос на регистрацию нового пользователя."""

        if {'first_name', 'last_name', 'email', 'password', 'company', 'position'}.\
                issubset(request.data):
            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = []
                # noinspection PyTypeChecker
                for item in password_error:
                    error_array.append(item)
                return JsonResponse({'Status': False,
                                     'Errors': {'password': error_array}},
                                    status=400)
            else:
                user_serializer = UserSerializer(data=request.data)
                if user_serializer.is_valid():
                    user = user_serializer.save()
                    user.set_password(request.data['password'])
                    user.save()
                    return JsonResponse({'Status': True}, status=201)
                else:
                    return JsonResponse({'Status': False,
                                         'Errors': user_serializer.errors},
                                        status=400)
        return JsonResponse({'Status': False,
                             'Errors': 'Не указаны все необходимые аргументы'},
                            status=400)


class ConfirmAccount(APIView):
    """Класс для подтверждения почтового адреса."""

    def post(self, request, *args, **kwargs):
        """Подтверждает почтовый адрес пользователя по токену."""

        if {'email', 'token'}.issubset(request.data):
            token = ConfirmEmailToken.objects.filter(user__email=request.data['email'],
                                                     key=request.data['token']).first()
            if token:
                token.user.is_active = True
                token.user.save()
                token.delete()
                return JsonResponse({'Status': True}, status=200)
            else:
                return JsonResponse({'Status': False,
                                     'Errors': 'Неправильно указан токен или email'},
                                    status=400)
        return JsonResponse({'Status': False,
                             'Errors': 'Не указаны все необходимые аргументы'},
                            status=400)


class AccountDetails(APIView):
    """Класс для управления персональными данными пользователя."""

    def get(self, request: Request, *args, **kwargs):
        """Получение данных текущего пользователя."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False,
                                 'Error': 'Требуется авторизация.'},
                                status=401)

        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        """Обновление данных пользователя."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False,
                                 'Error': 'Требуется авторизация.'},
                                status=401)
        if 'password' in request.data:
            errors = {}

            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = []
                # noinspection PyTypeChecker
                for item in password_error:
                    error_array.append(item)
                return JsonResponse({'Status': False,
                                     'Errors': {'password': error_array}},
                                    status=400)
            else:
                request.user.set_password(request.data['password'])

        user_serializer = UserSerializer(request.user,
                                         data=request.data,
                                         partial=True)
        if user_serializer.is_valid():
            user_serializer.save()
            return JsonResponse({'Status': True}, status=200)
        else:
            return JsonResponse({'Status': False,
                                 'Errors': user_serializer.errors},
                                status=400)


class LoginAccount(APIView):
    """Класс для авторизации пользователей."""

    def post(self, request, *args, **kwargs):
        """Аутентификация пользователя."""

        if {'email', 'password'}.issubset(request.data):
            user = authenticate(request, username=request.data['email'],
                                password=request.data['password'])
            if user is not None:
                if user.is_active:
                    token, _ = Token.objects.get_or_create(user=user)
                    return JsonResponse({'Status': True, 'Token': token.key},
                                        status=200)
            return JsonResponse({'Status': False,
                                 'Errors': 'Не удалось авторизовать'},
                                status=400)
        return JsonResponse({'Status': False,
                             'Errors': 'Не указаны все необходимые аргументы'},
                            status=400)


class ContactView(APIView):
    """Класс для управления контактными данными пользователя."""

    def get(self, request, *args, **kwargs):
        """Получение списка контактных данных пользователя."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Требуется авторизация.'},
                                status=401)

        contact = Contact.objects.filter(
            user_id=request.user.id)
        serializer = ContactSerializer(contact, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        """Добавление новых контактов."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False,
                                 'Error': 'Требуется авторизация.'},
                                status=401)

        if {'city', 'street', 'phone'}.issubset(request.data):
            data = request.data.copy()
            data.update({'user': request.user.id})
            serializer = ContactSerializer(data=data)

            if serializer.is_valid():
                serializer.save()
                return JsonResponse({'Status': True}, status=201)
            else:
                return JsonResponse({'Status': False,
                                     'Errors': serializer.errors},
                                    status=400)

        return JsonResponse({'Status': False,
                             'Errors': 'Не указаны все необходимые аргументы'},
                            status=400)

    def delete(self, request, *args, **kwargs):
        """Удаление контакт."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False,
                                 'Error': 'Требуется авторизация.'},
                                status=401)

        items_sting = request.data.get('items')
        if items_sting:
            items_list = items_sting.split(',')
            query = Q()
            objects_deleted = False
            for contact_id in items_list:
                if contact_id.isdigit():
                    query = query | Q(user_id=request.user.id, id=contact_id)
                    objects_deleted = True

            if objects_deleted:
                deleted_count = Contact.objects.filter(query).delete()[0]
                if deleted_count > 0:
                    return JsonResponse({'Status': True,
                                         'Удалено объектов': deleted_count},
                                        status=200)
                else:
                    return JsonResponse({'Status': False,
                                         'Error': 'Контакты не найдены'},
                                        status=404)
        return JsonResponse({'Status': False,
                             'Errors': 'Не указаны все необходимые аргументы'},
                            status=400)

    def put(self, request, *args, **kwargs):
        """Обновление существующего контакта."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False,
                                 'Error': 'Требуется авторизация.'},
                                status=401)

        if 'id' in request.data:
            if request.data['id'].isdigit():
                contact = Contact.objects.filter(id=request.data['id'],
                                                 user_id=request.user.id).first()
                if contact:
                    serializer = ContactSerializer(contact,
                                                   data=request.data,
                                                   partial=True)
                    if serializer.is_valid():
                        serializer.save()
                        return JsonResponse({'Status': True},
                                            status=200)
                    else:
                        return JsonResponse({'Status': False,
                                             'Errors': serializer.errors},
                                            status=400)
        return JsonResponse({'Status': False,
                             'Errors': 'Не указаны все необходимые аргументы'},
                            status=400)

