FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install --upgrade pip

# Устанавливаем рабочую директорию в контейнере
WORKDIR /app

# Копируем файл зависимостей перед копированием всего кода
COPY requirements.txt .

# Устанавливаем Python-зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем оставшиеся файлы проекта
COPY . .

# Собираем статику
RUN mkdir -p /app/staticfiles && \
    python manage.py collectstatic --noinput --clear || echo "Static files collection skipped"

# Открываем порт 8000
EXPOSE 8000

# Запускаем Gunicorn
CMD ["gunicorn", "orders.wsgi:application", "--bind", "0.0.0.0:8000"]
