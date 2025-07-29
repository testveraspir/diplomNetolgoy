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
from backend.serializers import ShopSerializer, OrderSerializer
from backend.signals import new_user_registered, new_order


class PartnerUpdate(APIView):
    """Класс для обновления прайс-листа магазина."""

    def post(self, request, *args, **kwargs):
        """Обновление прайс-листа магазина из YAML-файла."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False,
                                 'Error': 'Требуется авторизация.'},
                                status=401)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False,
                                 'Error': 'Только для магазинов'},
                                status=403)

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
                shop, _ = Shop.objects.get_or_create(name=data['shop'],
                                                     user_id=request.user.id)

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
        return JsonResponse({'Status': False,
                             'Errors': 'Не указаны все необходимые аргументы'},
                            status=400)


class PartnerState(APIView):
    """Класс для управления статусом магазина."""

    def get(self, request, *args, **kwargs):
        """Получить текущий статус магазина."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False,
                                 'Error': 'Требуется авторизация.'},
                                status=401)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False,
                                 'Error': 'Только для магазинов'},
                                status=403)

        shop = request.user.shop
        serializer = ShopSerializer(shop)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        """Изменить статус магазина."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False,
                                 'Error': 'Требуется авторизация.'},
                                status=401)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False,
                                 'Error': 'Только для магазинов'},
                                status=403)

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
                             'Errors': 'Не указаны все необходимые аргументы'},
                            status=400)


class PartnerOrders(APIView):
    """Класс для получения заказов поставщиками."""

    def get(self, request, *args, **kwargs):
        """Получение списка заказов для магазина."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False,
                                 'Error': 'Требуется авторизация.'},
                                status=401)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False,
                                 'Error': 'Только для магазинов'},
                                status=403)

        order = Order.objects.filter(
            ordered_items__product_info__shop__user_id=request.user.id)\
            .exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter')\
            .select_related('contact').annotate(
            total_sum=Sum(F('ordered_items__quantity')
                          * F('ordered_items__product_info__price'))).distinct()

        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data)
