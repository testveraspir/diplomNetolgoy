from celery import shared_task
from django.core.mail import EmailMultiAlternatives


@shared_task
def send_email(subject, message, from_email, to):
    """
    Отправляет электронное письмо асинхронно через Celery.
    :param subject: Тема письма
    :param message: Текст письма
    :param from_email: Email отправителя
    :param to: Email получателя или список получателей
    :return: None
    """

    msg = EmailMultiAlternatives(
        subject=subject,
        body=message,
        from_email=from_email,
        to=to
    )
    msg.send()
