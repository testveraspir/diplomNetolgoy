from distutils.util import strtobool
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db.models import Sum, F
from django.http import JsonResponse
from requests import get
from rest_framework.response import Response
from rest_framework.views import APIView
from yaml import load as load_yaml, Loader
from backend.models import (Shop, Category, Product, ProductInfo,
                            Parameter, ProductParameter, Order)
from backend.permissions import IsShopUser, IsAuthenticated
from backend.serializers import ShopSerializer, OrderSerializer
from backend.signals import new_user_registered, new_order
from django.db import transaction


class PartnerUpdate(APIView):
    """Класс для обновления прайс-листа магазина."""

    permission_classes = [IsAuthenticated, IsShopUser]

    def post(self, request, *args, **kwargs):
        """Обновление прайс-листа магазина из YAML-файла."""

        url = request.data.get('url')
        if url:
            validate_url = URLValidator()
            try:
                validate_url(url)
            except ValidationError as e:
                return JsonResponse({'Status': False,
                                     'Error': str(e)},
                                    status=400)
            else:
                stream = get(url).content
                data = load_yaml(stream, Loader=Loader)

                with transaction.atomic():

                    shop, _ = Shop.objects.get_or_create(name=data['shop'],
                                                         user_id=request.user.id)
                    if shop.user_id != request.user.id:
                        raise ValueError("Импорт возможен только для своего магазина")

                    for category in data['categories']:
                        category_object, _ = Category.objects.get_or_create(id=category['id'],
                                                                            name=category['name'])
                        category_object.shops.add(shop.id)
                        category_object.save()

                    for item in data['goods']:
                        product, _ = Product.objects.get_or_create(name=item['name'],
                                                                   category_id=item['category'])

                        # пытаемся найти существующий товар с совпадающими параметрами
                        existing_product = ProductInfo.objects.filter(product_id=product.id,
                                                                      external_id=item['id'],
                                                                      model=item['model'],
                                                                      price=item['price'],
                                                                      price_rrc=item['price_rrc'],
                                                                      shop_id=shop.id).first()
                        # если товар найден - обновляем количество
                        if existing_product:
                            existing_product.quantity += item['quantity']
                            existing_product.save()
                            product_info = existing_product
                        # если не найден - создаём новый
                        else:
                            product_info = ProductInfo.objects.create(product_id=product.id,
                                                                      external_id=item['id'],
                                                                      model=item['model'],
                                                                      price=item['price'],
                                                                      price_rrc=item['price_rrc'],
                                                                      quantity=item['quantity'],
                                                                      shop_id=shop.id)

                        for name, value in item['parameters'].items():
                            parameter_object, _ = Parameter.objects.get_or_create(name=name)
                            # удаляем старые параметры перед созданием новых
                            ProductParameter.objects.filter(product_info_id=product_info.id,
                                                            parameter_id=parameter_object.id
                                                            ).delete()
                            ProductParameter.objects.create(product_info_id=product_info.id,
                                                            parameter_id=parameter_object.id,
                                                            value=value)
                    return JsonResponse({'Status': True}, status=200)
        return JsonResponse({'Status': False,
                             'Errors': 'Необходимые поля отсутствуют.'},
                            status=400)


class PartnerState(APIView):
    """Класс для управления статусом магазина."""

    permission_classes = [IsAuthenticated, IsShopUser]

    def get(self, request, *args, **kwargs):
        """Получить текущий статус магазина."""

        shop = request.user.shop
        serializer = ShopSerializer(shop)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        """Изменить статус магазина."""

        state = request.data.get('state')
        if state:
            try:
                Shop.objects.filter(user_id=request.user.id)\
                    .update(state=strtobool(state))
                return JsonResponse({'Status': True},
                                    status=200)
            except ValueError as error:
                return JsonResponse({'Status': False,
                                     'Errors': str(error)},
                                    status=400)
        return JsonResponse({'Status': False,
                             'Errors': 'Необходимые поля отсутствуют.'},
                            status=400)


class PartnerOrders(APIView):
    """Класс для получения заказов поставщиками."""

    permission_classes = [IsAuthenticated, IsShopUser]

    def get(self, request, *args, **kwargs):
        """Получение списка заказов для магазина."""

        order = Order.objects.filter(
            ordered_items__product_info__shop__user_id=request.user.id
        ).exclude(
            state='basket'
        ).prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter'
        ).select_related(
            'contact'
        ).annotate(
            total_sum=Sum(F('ordered_items__quantity')
                          * F('ordered_items__product_info__price'))
        ).distinct()

        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data)
