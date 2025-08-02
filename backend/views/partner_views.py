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
from django.core.cache import cache


class PartnerUpdate(APIView):
    """Класс для обновления прайс-листа магазина через URL или YAML-файл."""

    permission_classes = [IsAuthenticated, IsShopUser]

    def post(self, request, *args, **kwargs):
        """Принимает URL YAML-файла или YAML-файл и запускает импорт."""

        yaml_files = request.FILES.getlist('yaml_file')
        url = request.data.get('url')

        if not (url or yaml_files):
            return JsonResponse({'Status': False,
                                 'Error': 'Укажите URL или загрузите YAML-файл'},
                                status=400)

        if url and yaml_files:
            return JsonResponse({'Status': False,
                                 'Error': 'Укажите только URL или только файл'},
                                status=400)

        if yaml_files and len(yaml_files) > 1:
            return JsonResponse({'Status': False,
                                 'Error': 'Можно загружать только один YAML-файл'},
                                status=400)
        try:
            if url:
                validate_url = URLValidator()
                validate_url(url)
                task = do_import.delay(url, request.user.id)
            elif yaml_files:
                yaml_file = yaml_files[0]
                if not yaml_file.name.endswith(('.yaml', '.yml')):
                    raise ValidationError('Файл должен быть в формате YAML (.yaml/.yml)')
                if yaml_file.size > 10 * 1024 * 1024:
                    raise ValueError('Размер файла не должен превышать 10MB')
                file_content = yaml_file.read()
                task = do_import.delay(file_content, request.user.id)

            cache.set(f"task_owner_{task.id}", request.user.id, timeout=86400)
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
        except Exception as e:
            return JsonResponse({'Status': False,
                                 'Error': f'Ошибка сервера: {str(e)}'},
                                status=500)

    def get(self, request, task_id, *args, **kwargs):
        """Проверяет статус выполнения задачи."""

        task = AsyncResult(task_id)

        if not task:
            return JsonResponse({'Status': False,
                                 'Error': 'Задача не найдена.'},
                                status=404)

        task_owner_id = cache.get(f'task_owner_{task_id}')
        if task_owner_id is None:
            return JsonResponse({'Status': False,
                                 'Error': 'Задачи не существует.'},
                                status=404)

        task_owner_id = cache.get(f'task_owner_{task_id}')
        if task_owner_id != request.user.id:
            return JsonResponse({'Status': False,
                                 'Error': 'У вас нет прав на просмотр этой задачи.'},
                                status=403)

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

        if state is None:
            return JsonResponse({'Status': False,
                                 'Errors': 'Поле "state" отсутствует.'},
                                status=400)

        if not isinstance(state, bool):
            return JsonResponse({'Status': False,
                                 'Errors': 'Поле "state" должно быть true или false.'},
                                status=400)

        Shop.objects.filter(user_id=request.user.id).update(state=state)
        return JsonResponse({'Status': True}, status=200)


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
