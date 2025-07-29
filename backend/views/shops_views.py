from rest_framework.request import Request
from django.db import IntegrityError
from django.db.models import Q, Sum, F
from django.http import JsonResponse
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from backend.models import Shop, Category, ProductInfo, Order
from backend.serializers import (CategorySerializer, ShopSerializer,
                                 ProductInfoSerializer, OrderSerializer)
from backend.signals import new_user_registered, new_order


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


class OrderView(APIView):
    """Класс для получения и размещения заказов пользователями."""

    def get(self, request, *args, **kwargs):
        """Получение списка заказов пользователя (исключая корзину)."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False,
                                 'Error': 'Требуется авторизация.'},
                                status=401)

        order = Order.objects.filter(
            user_id=request.user.id).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter')\
            .select_related('contact').annotate(
            total_sum=Sum(F('ordered_items__quantity')
                          * F('ordered_items__product_info__price'))).distinct()

        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        """Оформление заказа из корзины покупок."""

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False,
                                 'Error': 'Log in required'},
                                status=401)

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
        return JsonResponse({'Status': False,
                             'Errors': 'Не указаны все необходимые аргументы'},
                            status=400)
