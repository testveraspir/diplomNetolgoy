from django.db import transaction
from django.db.models import Sum, F
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework.views import APIView
from backend.models import ProductInfo, Order, OrderItem
from backend.permissions import IsAuthenticated
from backend.serializers import OrderItemSerializer, OrderSerializer


class BasketView(APIView):
    """
    Класс для работы с корзиной покупок.
    При добавлении товаров в корзину резервирует
    указанное количество товаров в магазине.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """Получение содержимого корзины."""

        basket = Order.objects.filter(
            user_id=request.user.id, state='basket'
        ).prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter'
        ).annotate(
            total_sum=Sum(F('ordered_items__quantity') * F(
                'ordered_items__product_info__price'))
        ).distinct()

        serializer = OrderSerializer(basket, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        """Добавление товаров в корзину с резервированием количества в магазине."""

        items_list = request.data.get('items')

        if items_list:

            # предварительная проверка наличия товаров перед транзакцией
            pre_check_errors = []
            product_infos = {}

            if not isinstance(items_list, list):
                pre_check_errors.append('items должен быть списком')
                return JsonResponse({'Status': False,
                                     'Errors': pre_check_errors},
                                    status=400)

            for order_item_data in items_list:
                product_info_id = order_item_data.get('product_info')
                quantity = order_item_data.get('quantity')

                if not product_info_id or not quantity:
                    pre_check_errors.append('Не указаны product_info или quantity')
                    continue

                if type(product_info_id) is not int or type(quantity) is not int:
                    pre_check_errors.append('product_info и quantity должны быть целыми числами')
                    continue

                try:
                    product_info = ProductInfo.objects.get(id=product_info_id)
                    product_infos[product_info_id] = product_info

                    if product_info.quantity < quantity:
                        pre_check_errors.append(
                            f"Недостаточно товара '{product_info.product.name}'."
                            f" Доступно: {product_info.quantity},"
                            f" Запрошено: {quantity}")
                except ProductInfo.DoesNotExist:
                    pre_check_errors.append(f"Товар с id {product_info_id} не найден")

            if pre_check_errors:
                return JsonResponse({'Status': False,
                                     'Errors': pre_check_errors},
                                    status=400)

            # если предварительная проверка прошла успешно, начинаем транзакцию
            try:
                with transaction.atomic():
                    basket, _ = Order.objects.get_or_create(user_id=request.user.id,
                                                            state='basket')
                    objects_created = 0

                    for order_item_data in items_list:
                        product_info_id = order_item_data.get('product_info')
                        quantity = order_item_data.get('quantity')
                        product_info = product_infos[product_info_id]

                        # уменьшаем количество товара
                        ProductInfo.objects.filter(id=product_info_id,
                                                   quantity__gte=quantity).update(
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
                    return JsonResponse({'Status': True,
                                         'Создано объектов': objects_created},
                                        status=201)
            except Exception as e:
                return JsonResponse({'Status': False,
                                     'Errors': [str(e)] if not isinstance(e, (list, dict)) else e},
                                    status=400)
        return JsonResponse({'Status': False,
                             'Errors': 'Необходимые поля отсутствуют.'},
                            status=400)

    def delete(self, request, *args, **kwargs):
        """Удаление товаров из корзины с возвратом количества в магазин."""

        items_string = request.data.get('items')
        if not items_string:
            return JsonResponse({'Status': False,
                                 'Errors': 'Не указаны товары для удаления'},
                                status=400)

        try:
            items_list = [int(item) for item in items_string.split(',')
                          if item.isdigit()]
        except (ValueError, AttributeError):
            return JsonResponse({'Status': False,
                                 'Errors': 'Некорректный формат списка ID товаров.'
                                           ' Ожидается строка вида: "1,2,3"'},
                                status=400)

        try:
            with transaction.atomic():
                # получаем корзину пользователя
                basket = Order.objects.filter(user_id=request.user.id,
                                              state='basket').first()
                if not basket:
                    return JsonResponse({'Status': False,
                                         'Errors': 'Корзина не найдена'},
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

                return JsonResponse({'Status': True,
                                     'Удалено объектов': deleted_count},
                                    status=200)
        except Exception as e:
            return JsonResponse({'Status': False,
                                 'Errors': str(e)},
                                status=400)

    def put(self, request, *args, **kwargs):
        """Изменение количество товаров в корзине с обновлением остатков в магазине."""

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

                    if not order_item_id or not isinstance(order_item_id, int)\
                            or not isinstance(new_quantity, int) or new_quantity < 0:
                        errors.append(f'Неверные данные для позиции заказа: {item_data}')
                        continue

                    try:
                        Order.objects.get(user_id=request.user.id, state='basket')
                    except Order.DoesNotExist:
                        errors.append('У вас нет активной корзины')
                        continue

                    try:
                        order_item = OrderItem.objects.get(id=order_item_id,
                                                           order__user_id=request.user.id,
                                                           order__state='basket')
                    except OrderItem.DoesNotExist:
                        errors.append(f"Позиция заказа с id {order_item_id}"
                                      f" не найдена в вашей корзине")
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
                    ProductInfo.objects.filter(id=product_info.id,
                                               quantity__gte=new_quantity).update(
                        quantity=F('quantity') - new_quantity
                    )

                    # обновляем количество в позиции заказа
                    order_item.quantity = new_quantity
                    order_item.save()
                    objects_updated += 1

                if errors:
                    # если были ошибки, откатываем транзакцию и возвращаем ошибки
                    raise ValueError(errors)

                return JsonResponse({'Status': True,
                                     'Обновлено объектов': objects_updated},
                                    status=200)
        except Exception as e:
            return JsonResponse({'Status': False,
                                 'Errors': [str(e)] if not isinstance(e, (list, dict)) else e},
                                status=400)
