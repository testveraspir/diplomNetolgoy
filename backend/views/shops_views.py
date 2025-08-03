from rest_framework.request import Request
from django.db import IntegrityError
from django.db.models import Q, Sum, F
from django.http import JsonResponse
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from backend.models import Shop, Category, ProductInfo, Order
from backend.permissions import IsAuthenticated
from backend.serializers import (CategorySerializer, ShopSerializer, Contact,
                                 ProductInfoSerializer, OrderSerializer)
from backend.signals import new_order


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

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """Получение списка заказов пользователя (исключая корзину)."""

        order = Order.objects.filter(
            user_id=request.user.id
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

    def post(self, request, *args, **kwargs):
        """Оформление заказа из корзины покупок."""

        if {'id', 'contact'}.issubset(request.data):

            try:
                order_id = int(request.data['id'])
                contact_id = int(request.data['contact'])
            except (ValueError, TypeError):
                return JsonResponse({'Status': False,
                                     'Errors': 'Поля "id" и "contact" должны быть числами.'},
                                    status=400)

            try:
                order = Order.objects.filter(user_id=request.user.id,
                                             id=order_id,
                                             state='basket').first()
                if not order:
                    return JsonResponse({'Status': False,
                                         'Errors': 'Корзина не найдена или не принадлежит пользователю'},
                                        status=404)
                try:
                    Contact.objects.get(id=contact_id, user=request.user)
                except Contact.DoesNotExist:
                    return JsonResponse({'Status': False,
                                         'Errors': 'Контакт не найден'},
                                        status=404)
                is_updated = Order.objects.filter(user_id=request.user.id,
                                                  id=order_id).update(contact_id=contact_id,
                                                                      state='new')

            except IntegrityError as error:
                return JsonResponse({'Status': False,
                                     'Errors': f'Ошибка базы данных: {error}'},
                                    status=400)
            else:
                if is_updated:
                    new_order.send(sender=self.__class__, user_id=request.user.id)
                    return JsonResponse({'Status': True}, status=200)
        return JsonResponse({'Status': False,
                             'Errors': 'Необходимые поля отсутствуют.'},
                            status=400)
