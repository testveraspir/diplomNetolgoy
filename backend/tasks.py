from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from yaml import load as load_yaml, Loader, YAMLError
from requests import get
from requests.exceptions import RequestException
from django.db import transaction
from backend.models import (Shop, User, Category, Product,
                            ProductInfo, Parameter, ProductParameter)

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
def do_import(self, url: str, user_id: int) -> None:
    """Асинхронно импортирует данные партнёра из YAML-файла по URL."""

    try:
        response = get(url)
        response.raise_for_status()
        stream = response.content
        data = load_yaml(stream, Loader=Loader)

        with transaction.atomic():

            shop, _ = Shop.objects.get_or_create(name=data['shop'],
                                                 user_id=user_id)
            if shop.user_id != user_id:
                raise ValueError("Импорт возможен только для своего магазина")

            for category in data['categories']:
                category_object, _ = Category.objects.get_or_create(id=category['id'],
                                                                    name=category['name'])
                category_object.shops.add(shop.id)
                category_object.save()

            for item in data['goods']:
                product, _ = Product.objects.get_or_create(name=item['name'],
                                                           category_id=item['category'])

                # пытаемся найти существующий товар с совпадающими параметрами
                existing_product = ProductInfo.objects.filter(product_id=product.id,
                                                              external_id=item['id'],
                                                              model=item['model'],
                                                              price=item['price'],
                                                              price_rrc=item['price_rrc'],
                                                              shop_id=shop.id).first()
                # если товар найден - обновляем количество
                if existing_product:
                    existing_product.quantity += item['quantity']
                    existing_product.save()
                    product_info = existing_product
                # если не найден - создаём новый
                else:
                    product_info = ProductInfo.objects.create(product_id=product.id,
                                                              external_id=item['id'],
                                                              model=item['model'],
                                                              price=item['price'],
                                                              price_rrc=item['price_rrc'],
                                                              quantity=item['quantity'],
                                                              shop_id=shop.id)

                for name, value in item['parameters'].items():
                    parameter_object, _ = Parameter.objects.get_or_create(name=name)
                    # удаляем старые параметры перед созданием новых
                    ProductParameter.objects.filter(product_info_id=product_info.id,
                                                    parameter_id=parameter_object.id
                                                    ).delete()
                    ProductParameter.objects.create(product_info_id=product_info.id,
                                                    parameter_id=parameter_object.id,
                                                    value=value)

    except RequestException as e:
        self.retry(exc=e, countdown=60)
    except YAMLError as e:
        raise ValueError(f'Ошибка парсинга YAML: {str(e)}')
    except KeyError as e:
        raise ValueError(f'Отсутствует обязательное поле: {str(e)}')
    except Exception as e:
        raise ValueError(f'Ошибка импорта: {str(e)}')
