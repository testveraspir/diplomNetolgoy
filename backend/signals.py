from typing import Type

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from django_rest_passwordreset.signals import reset_password_token_created
from backend.tasks import send_email
from backend.models import ConfirmEmailToken, User

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
    отправляет уведомление пользователю.

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
