# Структура проекта

```plaintext
project/
├── backend/                     # Основное Django-приложение
│   ├── migrations/              # Миграции БД
│   ├── static/                  # Статические файлы (CSS/JS)
│   ├── templates/               # HTML-шаблоны
│   ├── views/                   # Представления
│   ├── admin.py                 # Настройки админки
│   ├── apps.py                  # Конфиг приложения
│   ├── excel_utils.py           # Работа с Excel
│   ├── models.py                # Модели данных
│   ├── permissions.py           # Права доступа
│   ├── serializers.py           # Сериализаторы
│   ├── signals.py               # Сигналы Django
│   ├── tasks.py                 # Задачи Celery
│   ├── urls.py                  # URL-маршруты приложения
│   └── validators.py            # Валидаторы данных
│
├── data/                        # Данные для загрузки в базу данных
├── documents/                   # Документация проекта
│   ├── img_documentation/       # Изображения для документации
│   ├── Commands.md              # Команды проекта
│   ├── Documentation.md         # API документация
│   ├── PROJECT_STRUCTURE.md     # Описание структуры проекта
│   └── TASK.md                  # Задание
│
├── locale/                      # Локализация (переводы)
│
├── orders/
│   ├── __init__.py
│   ├── asgi.py                  # ASGI-конфигурация
│   ├── celery.py                # Конфигурация Celery
│   ├── settings.py              # Настройки Django
│   ├── urls.py                  # Основные URL-маршруты
│   ├── wsgi.py                  # WSGI-конфигурация
│
├── tests/                       # Тесты
│
├── .env                         # Переменные окружения
├── .gitignore                   # Игнорируемые файлы для Git
├── docker-compose.yml           # Конфигурация Docker Compose
├── Dockerfile                   # Основной Dockerfile
├── Dockerfile.celery            # Dockerfile для Celery
├── manage.py                    # Управление Django
├── README.md                    # Описание проекта
├── requirements.txt             # Зависимости Python
└── run_celery.sh                # Скрипт запуска Celery

```
