from distutils.util import strtobool
from rest_framework.request import Request
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum, F
from django.http import JsonResponse
from requests import get
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from yaml import load as load_yaml, Loader

from backend.models import (Shop, Category, Product,
                            ProductInfo, Parameter, ProductParameter,
                            Order, OrderItem, Contact, ConfirmEmailToken)
from backend.serializers import (UserSerializer, CategorySerializer, ShopSerializer,
                                 ProductInfoSerializer, OrderItemSerializer, OrderSerializer,
                                 ContactSerializer)
from backend.signals import new_user_registered, new_order


class RegisterAccount(APIView):
    """Класс для обработки запросов на регистрацию пользователей-покупателей."""

    def post(self, request, *args, **kwargs):
        """Обрабатывает запрос на регистрацию нового пользователя."""

        if {'first_name', 'last_name', 'email', 'password', 'company', 'position'}.issubset(request.data):
            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = []
                # noinspection PyTypeChecker
                for item in password_error:
                    error_array.append(item)
                return JsonResponse({'Status': False, 'Errors': {'password': error_array}}, status=400)
            else:
                user_serializer = UserSerializer(data=request.data)
                if user_serializer.is_valid():
                    user = user_serializer.save()
                    user.set_password(request.data['password'])
                    user.save()
                    return JsonResponse({'Status': True}, status=201)
                else:
                    return JsonResponse({'Status': False, 'Errors': user_serializer.errors}, status=400)
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)


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
            return JsonResponse({'Status': False, 'Error': 'Требуется авторизация.'},
                                status=401)

        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        """Обновление данных пользователя."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Требуется авторизация.'},
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
                return JsonResponse({'Status': False, 'Errors': {'password': error_array}},
                                    status=400)
            else:
                request.user.set_password(request.data['password'])

        user_serializer = UserSerializer(request.user, data=request.data, partial=True)
        if user_serializer.is_valid():
            user_serializer.save()
            return JsonResponse({'Status': True}, status=200)
        else:
            return JsonResponse({'Status': False, 'Errors': user_serializer.errors}, status=400)


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
                    return JsonResponse({'Status': True, 'Token': token.key}, status=200)
            return JsonResponse({'Status': False, 'Errors': 'Не удалось авторизовать'},
                                status=400)
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'},
                            status=400)


class CategoryView(ListAPIView):
    """Класс для просмотра категорий."""

    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class ShopView(ListAPIView):
    """Класс для просмотра списка магазинов."""

    queryset = Shop.objects.filter(state=True)
    serializer_class = ShopSerializer


class ProductInfoView(APIView):
    """Класс для поиска товаров в магазинах."""

    def get(self, request: Request, *args, **kwargs):
        """Получение списка товаров с возможностью фильтрации."""

        query = Q(shop__state=True)
        shop_id = request.query_params.get('shop_id')
        category_id = request.query_params.get('category_id')

        if shop_id:
            query = query & Q(shop_id=shop_id)
        if category_id:
            query = query & Q(product__category_id=category_id)

        queryset = ProductInfo.objects.filter(
            query).select_related(
            'shop', 'product__category').prefetch_related(
            'product_parameters__parameter').distinct()

        serializer = ProductInfoSerializer(queryset, many=True)

        return Response(serializer.data)


class BasketView(APIView):
    """
    Класс для работы с корзиной покупок.
    При добавлении товаров в корзину резервирует
    указанное количество товаров в магазине.
    """

    def get(self, request, *args, **kwargs):
        """Получение содержимого корзины."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Требуется авторизация.'}, status=401)
        basket = Order.objects.filter(
            user_id=request.user.id, state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()

        serializer = OrderSerializer(basket, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        """Добавление товаров в корзину с резервированием количества в магазине."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Требуется авторизация.'}, status=401)

        items_list = request.data.get('items')

        if items_list:

            # предварительная проверка наличия товаров перед транзакцией
            pre_check_errors = []
            product_infos = {}

            if not isinstance(items_list, list):
                pre_check_errors.append("items должен быть списком")
                return JsonResponse({'Status': False, 'Errors': pre_check_errors}, status=400)

            for order_item_data in items_list:
                product_info_id = order_item_data.get('product_info')
                quantity = order_item_data.get('quantity')

                if not product_info_id or not quantity:
                    pre_check_errors.append("Не указаны product_info или quantity")
                    continue

                try:
                    product_info = ProductInfo.objects.get(id=product_info_id)
                    product_infos[product_info_id] = product_info

                    if product_info.quantity < quantity:
                        pre_check_errors.append(
                            f"Недостаточно товара '{product_info.product.name}'."
                            f" Доступно: {product_info.quantity}, Запрошено: {quantity}")
                except ProductInfo.DoesNotExist:
                    pre_check_errors.append(f"Товар с id {product_info_id} не найден")

            if pre_check_errors:
                return JsonResponse({'Status': False, 'Errors': pre_check_errors}, status=400)

            # если предварительная проверка прошла успешно, начинаем транзакцию
            try:
                with transaction.atomic():
                    basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
                    objects_created = 0

                    for order_item_data in items_list:
                        product_info_id = order_item_data.get('product_info')
                        quantity = order_item_data.get('quantity')
                        product_info = product_infos[product_info_id]

                        # уменьшаем количество товара
                        ProductInfo.objects.filter(id=product_info_id, quantity__gte=quantity).update(
                            quantity=F('quantity') - quantity)

                        # проверяем, что обновление прошло успешно
                        updated_rows = ProductInfo.objects.filter(
                            id=product_info_id,
                            quantity=F('quantity') + quantity - quantity).count()

                        if not updated_rows:
                            raise ValueError(
                                f"Не удалось зарезервировать товар {product_info_id}."
                                f" Возможно, количество изменилось.")

                        # создаём позицию в заказе
                        order_item_data['order'] = basket.id
                        order_item_data['price'] = product_info.price
                        serializer = OrderItemSerializer(data=order_item_data)

                        if serializer.is_valid():
                            serializer.save()
                            objects_created += 1
                        else:
                            raise ValueError(serializer.errors)
                    return JsonResponse({'Status': True, 'Создано объектов': objects_created}, status=201)
            except Exception as e:
                return JsonResponse({'Status': False,
                                     'Errors': [str(e)] if not isinstance(e, (list, dict)) else e},
                                    status=400)
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'},
                            status=400)

    def delete(self, request, *args, **kwargs):
        """Удаление товаров из корзины с возвратом количества в магазин."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Требуется авторизация.'},
                                status=401)

        items_string = request.data.get('items')
        if not items_string:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны товары для удаления'},
                                status=400)

        try:
            items_list = [int(item) for item in items_string.split(',') if item.isdigit()]
        except ValueError:
            return JsonResponse({'Status': False, 'Errors': 'Неверный формат списка товаров'},
                                status=400)

        if not items_list:
            return JsonResponse({'Status': False, 'Errors': 'Некорректный список ID товаров'},
                                status=400)

        try:
            with transaction.atomic():
                # получаем корзину пользователя
                basket = Order.objects.filter(user_id=request.user.id, state='basket').first()
                if not basket:
                    return JsonResponse({'Status': False, 'Errors': 'Корзина не найдена'},
                                        status=404)

                # получаем все позиции для удаления с информацией о товарах
                order_items = OrderItem.objects.filter(order_id=basket.id,
                                                       id__in=items_list
                                                      ).select_related('product_info')

                # возвращаем товары на склад
                for item in order_items:
                    ProductInfo.objects.filter(id=item.product_info_id).update(
                        quantity=F('quantity') + item.quantity
                    )

                # удаляем позиции
                deleted_count, _ = order_items.delete()

                # если не удалили ни одного элемента, хотя запрос был
                if deleted_count == 0:
                    return JsonResponse({'Status': False,
                                         'Errors': 'Указанные товары не найдены в корзине'},
                                        status=400)

                return JsonResponse({'Status': True, 'Удалено объектов': deleted_count},
                                    status=200)
        except Exception as e:
            return JsonResponse({'Status': False, 'Errors': str(e)},
                                status=400)

    def put(self, request, *args, **kwargs):
        """Изменение количество товаров в корзине с обновлением остатков в магазине."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False,
                                 'Error': 'Требуется авторизация.'},
                                status=401)

        items_dict = request.data.get('items')

        if not items_dict:
            return JsonResponse({'Status': False,
                                 'Errors': 'Не указаны items для обновления'},
                                status=400)

        try:
            with transaction.atomic():
                objects_updated = 0
                errors = []

                for item_data in items_dict:
                    order_item_id = item_data.get('id')
                    new_quantity = item_data.get('quantity')

                    if not order_item_id or not isinstance(new_quantity, int) or new_quantity < 0:
                        errors.append(f"Неверные данные для позиции заказа: {item_data}")
                        continue

                    try:
                        order_item = OrderItem.objects.get(id=order_item_id,
                                                           order__user_id=request.user.id,
                                                           order__state='basket')
                    except OrderItem.DoesNotExist:
                        errors.append(f"Позиция заказа с id {order_item_id} не найдена в вашей корзине")
                        continue

                    product_info = order_item.product_info

                    # возвращаем старое количество товара на склад
                    ProductInfo.objects.filter(id=product_info.id)\
                        .update(quantity=F('quantity') + order_item.quantity)

                    # проверяем, достаточно ли товара на складе для нового количества
                    if product_info.quantity < new_quantity:

                        # возвращаем количество обратно, т.к. недостаточно товара
                        ProductInfo.objects.filter(id=product_info.id).update(
                            quantity=F('quantity') - order_item.quantity)
                        errors.append(
                            f"Недостаточно товара '{product_info.product.name}'."
                            f" Доступно: {product_info.quantity}, Запрошено: {new_quantity}"
                        )
                        continue

                    # обновляем количество товара на складе с учетом нового количества
                    ProductInfo.objects.filter(id=product_info.id, quantity__gte=new_quantity).update(
                        quantity=F('quantity') - new_quantity
                    )

                    # обновляем количество в позиции заказа
                    order_item.quantity = new_quantity
                    order_item.save()
                    objects_updated += 1

                if errors:
                    # если были ошибки, откатываем транзакцию и возвращаем ошибки
                    raise ValueError(errors)

                return JsonResponse({'Status': True, 'Обновлено объектов': objects_updated},
                                    status=200)
        except Exception as e:
            return JsonResponse({'Status': False,
                                 'Errors': [str(e)] if not isinstance(e, (list, dict)) else e},
                                status=400)


class PartnerUpdate(APIView):
    """Класс для обновления прайс-листа магазина."""

    def post(self, request, *args, **kwargs):
        """Обновление прайс-листа магазина из YAML-файла."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Требуется авторизация.'}, status=401)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        url = request.data.get('url')
        if url:
            validate_url = URLValidator()
            try:
                validate_url(url)
            except ValidationError as e:
                return JsonResponse({'Status': False, 'Error': str(e)}, status=400)
            else:
                stream = get(url).content
                data = load_yaml(stream, Loader=Loader)
                shop, _ = Shop.objects.get_or_create(name=data['shop'], user_id=request.user.id)

                for category in data['categories']:
                    category_object, _ = Category.objects.get_or_create(id=category['id'],
                                                                        name=category['name'])
                    category_object.shops.add(shop.id)
                    category_object.save()
                ProductInfo.objects.filter(shop_id=shop.id).delete()
                for item in data['goods']:
                    product, _ = Product.objects.get_or_create(name=item['name'],
                                                               category_id=item['category'])
                    product_info = ProductInfo.objects.create(product_id=product.id,
                                                              external_id=item['id'],
                                                              model=item['model'],
                                                              price=item['price'],
                                                              price_rrc=item['price_rrc'],
                                                              quantity=item['quantity'],
                                                              shop_id=shop.id)

                    for name, value in item['parameters'].items():
                        parameter_object, _ = Parameter.objects.get_or_create(name=name)
                        ProductParameter.objects.create(product_info_id=product_info.id,
                                                        parameter_id=parameter_object.id,
                                                        value=value)
                return JsonResponse({'Status': True}, status=200)
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'},
                            status=400)


class PartnerState(APIView):
    """Класс для управления статусом магазина."""

    def get(self, request, *args, **kwargs):
        """Получить текущий статус магазина."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Требуется авторизация.'}, status=401)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        shop = request.user.shop
        serializer = ShopSerializer(shop)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        """Изменить статус магазина."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Требуется авторизация.'}, status=401)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        state = request.data.get('state')
        if state:
            try:
                Shop.objects.filter(user_id=request.user.id).update(state=strtobool(state))
                return JsonResponse({'Status': True}, status=200)
            except ValueError as error:
                return JsonResponse({'Status': False, 'Errors': str(error)}, status=400)
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'},
                            status=400)


class PartnerOrders(APIView):
    """Класс для получения заказов поставщиками."""

    def get(self, request, *args, **kwargs):
        """Получение списка заказов для магазина."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Требуется авторизация.'}, status=401)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        order = Order.objects.filter(
            ordered_items__product_info__shop__user_id=request.user.id).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter').select_related('contact').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()

        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data)


class ContactView(APIView):
    """Класс для управления контактными данными пользователя."""

    def get(self, request, *args, **kwargs):
        """Получение списка контактных данных пользователя."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Требуется авторизация.'}, status=401)

        contact = Contact.objects.filter(
            user_id=request.user.id)
        serializer = ContactSerializer(contact, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        """Добавление новых контактов."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Требуется авторизация.'}, status=401)

        if {'city', 'street', 'phone'}.issubset(request.data):
            data = request.data.copy()
            data.update({'user': request.user.id})
            serializer = ContactSerializer(data=data)

            if serializer.is_valid():
                serializer.save()
                return JsonResponse({'Status': True}, status=201)
            else:
                return JsonResponse({'Status': False, 'Errors': serializer.errors}, status=400)

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)

    def delete(self, request, *args, **kwargs):
        """Удаление контакт."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Требуется авторизация.'}, status=401)

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
                    return JsonResponse({'Status': True, 'Удалено объектов': deleted_count},
                                        status=200)
                else:
                    return JsonResponse({'Status': False, 'Error': 'Контакты не найдены'}, status=404)
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'},
                            status=400)

    def put(self, request, *args, **kwargs):
        """Обновление существующего контакта."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Требуется авторизация.'}, status=401)

        if 'id' in request.data:
            if request.data['id'].isdigit():
                contact = Contact.objects.filter(id=request.data['id'], user_id=request.user.id).first()
                if contact:
                    serializer = ContactSerializer(contact, data=request.data, partial=True)
                    if serializer.is_valid():
                        serializer.save()
                        return JsonResponse({'Status': True}, status=200)
                    else:
                        return JsonResponse({'Status': False, 'Errors': serializer.errors}, status=400)
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)


class OrderView(APIView):
    """Класс для получения и размещения заказов пользователями."""

    def get(self, request, *args, **kwargs):
        """Получение списка заказов пользователя (исключая корзину)."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Требуется авторизация.'}, status=401)

        order = Order.objects.filter(
            user_id=request.user.id).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter').select_related('contact').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()

        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        """Оформление заказа из корзины покупок."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=401)

        if {'id', 'contact'}.issubset(request.data):
            if request.data['id'].isdigit():
                try:
                    is_updated = Order.objects.filter(
                        user_id=request.user.id, id=request.data['id']).update(
                        contact_id=request.data['contact'],
                        state='new')
                except IntegrityError as error:
                    print(error)
                    return JsonResponse({'Status': False,
                                         'Errors': 'Неправильно указаны аргументы'},
                                        status=400)
                else:
                    if is_updated:
                        new_order.send(sender=self.__class__, user_id=request.user.id)
                        return JsonResponse({'Status': True}, status=200)
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'}, status=400)
