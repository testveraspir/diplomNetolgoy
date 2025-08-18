from django.test import TestCase
from unittest.mock import patch
from django.core.files import File
from io import BytesIO
from PIL import Image

from backend.tasks import generate_product_thumbnails, generate_user_thumbnails
from backend.models import Product, User, Category


class TestGenerateThumbnailsTasks(TestCase):
    """Тесты для задач Celery по генерации уменьшенных копий изображений."""

    def setUp(self):
        """
        Подготовка тестовых данных:
        - Создает тестовое изображение
        - Создает тестовую категорию
        - Создает тестовый продукт с основным изображением
        - Создает тестового пользователя с аватаром
        """

        image = Image.new('RGB', (1000, 1000), color='red')
        image_file = BytesIO()
        image.save(image_file, 'JPEG')
        image_file.seek(0)
        self.category = Category.objects.create(name="Test Category")
        self.image_file = File(image_file, name='test.jpg')
        self.product = Product.objects.create(name="Test Product",
                                              image=self.image_file,
                                              category=self.category)
        self.user = User.objects.create(email="test@example.com",
                                        avatar=self.image_file)

    @patch('backend.tasks.generate_and_save_thumbnails')
    def test_generate_product_thumbnails_success(self, mock_generate):
        """
        Позитивный тест создания уменьшенных копий для продукта:
        - Мокируется успешная генерация вариантов изображения
        - Проверяется статус 'success'
        - Проверяется количество созданных вариантов
        - Проверяется тип модели в ответе
        """

        mock_generate.return_value = {'400x400': 'path1', '200x200': 'path2'}
        result = generate_product_thumbnails(self.product.id)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(len(result['generated']), 2)
        self.assertEqual(result['model'], 'Product')

    def test_generate_product_thumbnails_product_not_found(self):
        """
        Тест обработки случая отсутствия продукта:
        - Вызывается задача с несуществующим ID продукта
        - Проверяется статус 'error'
        - Проверяется текст сообщения об ошибке
        """

        result = generate_product_thumbnails(999)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['reason'], 'Товар не найден')

    @patch('backend.tasks.generate_and_save_thumbnails')
    def test_generate_user_thumbnails_success(self, mock_generate):
        """
        Позитивный тест создания уменьшенных копий аватара пользователя:
        - Мокируется успешная генерация вариантов изображения
        - Проверяется статус 'success'
        - Проверяется количество созданных вариантов
        - Проверяется тип модели в ответе
        """

        mock_generate.return_value = {'200x200': 'path1', '100x100': 'path2'}
        result = generate_user_thumbnails(self.user.id)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(len(result['generated']), 2)
        self.assertEqual(result['model'], 'User')

    def test_generate_user_thumbnails_user_not_found(self):
        """
        Тест обработки случая отсутствия пользователя:
        - Вызывается задача с несуществующим ID пользователя
        - Проверяется статус 'error'
        - Проверяется текст сообщения об ошибке
        """

        result = generate_user_thumbnails(999)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['reason'], 'Пользователь не найден')
