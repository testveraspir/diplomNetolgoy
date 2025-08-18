import os
from typing import Type

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from django_rest_passwordreset.signals import reset_password_token_created
from backend.tasks import (send_email, send_email_with_attachment,
                           generate_product_thumbnails, generate_user_thumbnails)
from backend.models import ConfirmEmailToken, User, Order, Product
from backend.excel_utils import generate_invoice_excel

new_user_registered = Signal()

new_order = Signal()


@receiver(reset_password_token_created)
def password_reset_token_created(sender, instance, reset_password_token, **kwargs):
    """
    Сигнальная функция, автоматически вызываемая при создании токена сброса пароля.
    Использует Celery для асинхронной отправки email.

    :param sender: Класс представления, который отправил сигнал
    :param instance: Экземпляр представления, отправившего сигнал
    :param reset_password_token: Объект токена сброса пароля
    :param kwargs: Дополнительные аргументы сигнала
    :return: None
    """

    send_email.delay(
        subject=f"Сброс пароля для {reset_password_token.user.email}",
        message=f"Ваш токен для сброса: {reset_password_token.key}",
        from_email=settings.EMAIL_HOST_USER,
        to=[reset_password_token.user.email]
    )


@receiver(post_save, sender=User)
def new_user_registered_signal(sender: Type[User], instance: User, created: bool, **kwargs):
    """
     Сигнальный обработчик, который:
    - Срабатывает при создании нового пользователя (created=True)
    - Отправляет токен подтверждения email, если пользователь неактивен
    - Использует асинхронную отправку через Celery

    :param sender: Класс модели User
    :param instance: Экземпляр пользователя, который был сохранен
    :param created: Флаг, указывающий, что пользователь только что создан
    :param kwargs: Дополнительные аргументы сигнала
    :return: None
    """

    if created and not instance.is_active:

        token, _ = ConfirmEmailToken.objects.get_or_create(user_id=instance.pk)
        send_email.delay(
            subject=f"Подтверждение email {instance.email}",
            message=f"Ваш токен подтверждения: {token.key}",
            from_email=settings.EMAIL_HOST_USER,
            to=[instance.email]
        )


@receiver(new_order)
def new_order_signal(user_id, **kwargs):
    """
    Обрабатывает изменение статуса заказа, и
    отправляет уведомление пользователю и администратору.

    :param user_id: ID пользователя, оформившего заказ
    :param kwargs: Дополнительные параметры
    :return: None
    """

    user = User.objects.get(id=user_id)
    state = kwargs.get('state', 'new')

    state_messages = {
        'new': 'Заказ сформирован',
        'confirmed': 'Заказ подтвержден',
        'assembled': 'Заказ собран',
        'sent': 'Заказ отправлен',
        'delivered': 'Заказ доставлен',
        'canceled': 'Заказ отменен'

    }

    send_email.delay(
        subject=f"Статус заказа: {state}",
        message=state_messages.get(state, 'Статус вашего заказа изменен'),
        from_email=settings.EMAIL_HOST_USER,
        to=[user.email]
    )

    if state == 'new':
        _handle_new_order(user_id, user)


def _handle_new_order(user_id, user):
    """
    Обрабатывает новый заказ и
    отправляет накладную администратору

    :param user_id: ID пользователя, оформившего заказ
    :param user: Объект пользователя (User)
    """

    order = Order.objects.filter(user_id=user_id,
                                 state='new'
                                 ).prefetch_related(
        'ordered_items',
        'ordered_items__product_info',
        'ordered_items__product_info__product',
        'ordered_items__product_info__shop'
    ).first()

    if not order:
        return

    # Подготовка данных о товарах по магазинам
    shops_items = {}
    for item in order.ordered_items.all():
        shop_name = item.product_info.shop.name
        product_name = item.product_info.product.name
        item_info = f"{product_name} - {item.quantity} шт." \
                    f" x {item.product_info.price} руб."

        if shop_name not in shops_items:
            shops_items[shop_name] = []
        shops_items[shop_name].append(item_info)

    # Формирование списка товаров для email
    items_list = []
    for shop_name, products in shops_items.items():
        items_list.append(f"\n--- Магазин: {shop_name} ---")
        items_list.extend(products)

        shop_total = sum(
            item.product_info.price * item.quantity
            for item in order.ordered_items.all()
            if item.product_info.shop.name == shop_name
        )
        items_list.append(f"Итого по магазину: {shop_total} руб.")

    # Формирование тела письма
    email_body = f"""
        НАКЛАДНАЯ №{order.id}
        Дата: {order.dt.strftime('%H:%M %d.%m.%Y')}
        Клиент: {user.email}
        Контакт: Город {order.contact.city},
                Улица {order.contact.street},
                Телефон {order.contact.phone}

        Состав заказа:
        {chr(10).join(items_list)}

        Итого к оплате: {sum(item.product_info.price * item.quantity
                             for item in order.ordered_items.all())} руб.
        """

    # Генерация и отправка Excel-файла
    excel_data = generate_invoice_excel(order, user, shops_items)
    send_email_with_attachment.delay(
        subject=f"Накладная по заказу №{order.id}",
        message=email_body,
        from_email=settings.EMAIL_HOST_USER,
        to_email=[os.getenv("EMAIL_HOST_USER")],
        excel_data=excel_data,
        filename=f"invoice_{order.id}.xlsx"
    )


@receiver(post_save, sender=Product)
def process_product_image_on_save(sender, instance, created, **kwargs):
    """Сигнал для обработки изображений товаров после сохранения."""

    if not instance.image:
        if hasattr(instance, 'clear_products_thumbnails'):
            instance.clear_products_thumbnails()
        return

    if not created:
        try:
            old = Product.objects.get(id=instance.id)
            if old.image.name != instance.image.name:
                if hasattr(old, 'clear_products_thumbnails'):
                    old.clear_products_thumbnails()
        except Product.DoesNotExist:
            pass

    sizes = [(400, 400), (200, 200), (100, 100)]
    generate_product_thumbnails.delay(instance.id, sizes)


@receiver(post_save, sender=User)
def process_user_avatar_on_save(sender, instance, created, **kwargs):
    """Сигнал для обработки аватара пользователя после сохранения."""

    if not instance.avatar:
        if hasattr(instance, 'clear_thumbnails'):
            instance.clear_thumbnails()
        return

    if not created:
        try:
            old_user = User.objects.get(id=instance.id)
            if old_user.avatar.name != instance.avatar.name:
                if hasattr(old_user, 'clear_thumbnails'):
                    old_user.clear_thumbnails()
        except User.DoesNotExist:
            pass

    avatar_sizes = [(200, 200), (100, 100), (50, 50)]

    # Запуск асинхронной задачи
    generate_user_thumbnails.delay(user_id=instance.id,
                                   sizes=avatar_sizes)
    print(f"Thumbnail generation task started for user {instance.id}")
