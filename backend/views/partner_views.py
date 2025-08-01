from distutils.util import strtobool
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db.models import Sum, F
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework.views import APIView
from backend.models import Shop, Order
from backend.permissions import IsShopUser, IsAuthenticated
from backend.serializers import ShopSerializer, OrderSerializer
from backend.tasks import do_import
from celery.result import AsyncResult
from django.urls import reverse


class PartnerUpdate(APIView):
    """Класс для обновления прайс-листа магазина."""

    permission_classes = [IsAuthenticated, IsShopUser]

    def post(self, request, *args, **kwargs):
        """Принимает URL YAML-файла и запускает импорт."""

        url = request.data.get('url')
        if url:
            validate_url = URLValidator()
            try:
                validate_url(url)
                task = do_import.delay(url, request.user.id)
                status_url = reverse('backend:task-status', kwargs={'task_id': task.id})
                return JsonResponse({'Status': True,
                                     'message': 'Задача принята в обработку',
                                     'task_id': task.id,
                                     'status_url': status_url},
                                    status=202)
            except ValidationError as e:
                return JsonResponse({'Status': False,
                                     'Error': str(e)},
                                    status=400)
        return JsonResponse({'Status': False,
                             'Errors': 'Необходимые поля отсутствуют.'},
                            status=400)

    def get(self, request, task_id, *args, **kwargs):
        """Проверяет статус выполнения задачи."""

        task = AsyncResult(task_id)
        if not task:
            return JsonResponse({'Status': False,
                                 'Error': 'Задача не найдена.'},
                                status=404)

        if task.failed():
            return JsonResponse({'Status': False,
                                 'Error': str(task.result),
                                 'task_status': 'FAILED'},
                                status=400)
        elif task.ready():
            return JsonResponse({'Status': True,
                                 'task_status': 'SUCCESS'},
                                status=200)
        else:
            return JsonResponse({'Status': True,
                                 'task_status': 'PENDING'},
                                status=200)


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
