## Команды

### Сборка образов

Собирает все образы, описанные в docker-compose.yml
```bash
docker-compose build
```

### Запуск системы

Запускает все сервисы в фоновом режиме
```bash
docker-compose up -d
```

### Применение миграций к базе данных

```bash
docker-compose exec backend python manage.py migrate
```
### Создание суперпользователя

Создаёт администратора для доступа к Django-админке

```bash
docker-compose exec backend python manage.py createsuperuser
```

### Запуск всех тестов

```bash
docker-compose exec backend python manage.py test
```