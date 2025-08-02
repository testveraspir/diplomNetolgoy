from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from typing import Union
from yaml import safe_load, Loader, YAMLError
from requests import get
from requests.exceptions import RequestException
from django.db import transaction
from backend.models import (Shop, Category, Product, ProductInfo,
                            Parameter, ProductParameter)


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


@shared_task(bind=True)
def do_import(self, source: Union[str, bytes], user_id: int) -> None:
    """Асинхронно импортирует данные партнёра из YAML-файла."""

    try:
        if isinstance(source, str):
            response = get(source)
            response.raise_for_status()
            stream = response.content

        else:
            stream = source

        data = safe_load(stream)

        with transaction.atomic():
            shop, _ = Shop.objects.get_or_create(name=data['shop'],
                                                 user_id=user_id)

            for category in data['categories']:
                category_object, _ = Category.objects.get_or_create(id=category['id'],
                                                                    name=category['name'])
                category_object.shops.add(shop.id)
                category_object.save()

            for item in data['goods']:
                product, _ = Product.objects.get_or_create(name=item['name'],
                                                           category_id=item['category'])

                product_info, created = ProductInfo.objects.get_or_create(
                    product_id=product.id,
                    external_id=item['id'],
                    model=item['model'],
                    shop_id=shop.id,
                    defaults={
                        'price': item['price'],
                        'price_rrc': item['price_rrc'],
                        'quantity': item['quantity']
                    }
                )

                if not created:
                    # Обновляем существующий продукт
                    product_info.price = item['price']
                    product_info.price_rrc = item['price_rrc']
                    product_info.quantity += item['quantity']
                    product_info.save()

                # Обработка параметров
                for name, value in item['parameters'].items():
                    parameter_object, _ = Parameter.objects.get_or_create(name=name)

                    # Пытаемся найти существующий параметр
                    product_param, created = ProductParameter.objects.get_or_create(
                        product_info_id=product_info.id,
                        parameter_id=parameter_object.id,
                        defaults={'value': value}
                    )

                    if not created:
                        # Обновляем существующий параметр
                        product_param.value = value
                        product_param.save()

    except RequestException as e:
        self.retry(exc=e, countdown=60)
    except YAMLError as e:
        raise ValueError(f'Ошибка парсинга YAML: {str(e)}')
    except KeyError as e:
        raise ValueError(f'Отсутствует обязательное поле: {str(e)}')
    except Exception as e:
        raise ValueError(f'Ошибка импорта: {str(e)}')
