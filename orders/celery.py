from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from django.conf import settings


# Устанавливаем переменную окружения для настроек Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'orders.settings')

app = Celery('orders')

# Используем строку настроек для настройки Celery
app.config_from_object('django.conf:settings', namespace='CELERY')

# Загружаем задачи из всех зарегистрированных приложений Django
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
