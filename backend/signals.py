from typing import Type

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from django_rest_passwordreset.signals import reset_password_token_created

from backend.models import ConfirmEmailToken, User

new_user_registered = Signal()

new_order = Signal()


@receiver(reset_password_token_created)
def password_reset_token_created(sender, instance, reset_password_token, **kwargs):
    """
    Отправляет пользователю письмо со ссылкой для сброса пароля.

    :param sender: Класс представления, который отправил сигнал
    :param instance: Экземпляр представления, отправившего сигнал
    :param reset_password_token: Объект токена сброса пароля
    :param kwargs: Дополнительные аргументы сигнала
    :return: None
    """

    msg = EmailMultiAlternatives(
        # title:
        f"Токен для сброса пароля {reset_password_token.user}",
        # message:
        reset_password_token.key,
        # from:
        settings.EMAIL_HOST_USER,
        # to:
        [reset_password_token.user.email]
    )
    msg.send()


@receiver(post_save, sender=User)
def new_user_registered_signal(sender: Type[User], instance: User, created: bool, **kwargs):
    """
    Отправляет письмо с подтверждением email при регистрации нового пользователя.

    :param sender: Класс модели User
    :param instance: Экземпляр пользователя, который был сохранен
    :param created: Флаг, указывающий, что пользователь только что создан
    :param kwargs: Дополнительные аргументы сигнала
    :return: None
    """

    if created and not instance.is_active:
        token, _ = ConfirmEmailToken.objects.get_or_create(user_id=instance.pk)

        msg = EmailMultiAlternatives(
            # title:
            f"Токен для подтверждения регистрации {instance.email}",
            # message:
            token.key,
            # from:
            settings.EMAIL_HOST_USER,
            # to:
            [instance.email]
        )
        msg.send()


@receiver(new_order)
def new_order_signal(user_id, **kwargs):
    """
    Отправляет email пользователю при обновлении статуса заказа.

    :param user_id: ID пользователя, оформившего заказ
    :param kwargs:
    :return: Дополнительные параметры
    """

    user = User.objects.get(id=user_id)

    msg = EmailMultiAlternatives(
        # title:
        f"Обновление статуса заказа",
        # message:
        'Заказ сформирован',
        # from:
        settings.EMAIL_HOST_USER,
        # to:
        [user.email]
    )
    msg.send()
