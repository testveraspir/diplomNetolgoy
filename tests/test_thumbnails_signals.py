from django.test import TestCase
from unittest.mock import patch
from django.core.files import File
from io import BytesIO
from PIL import Image
from backend.models import Product, User, Category


class TestThumbnailsSignals(TestCase):
    """
    Тесты для сигналов обработки изображений товаров
    и аватаров пользователей.
    """

    def setUp(self):
        """
        Подготовка тестовых данных:
        - Создает тестовое изображение
        - Создает тестовую категорию товаров
        - Создает тестовый товар без изображения
        - Создает тестового пользователя без аватара
        """

        image = Image.new('RGB', (1000, 1000), color='red')
        image_file = BytesIO()
        image.save(image_file, 'JPEG')
        image_file.seek(0)
        self.image_file = File(image_file, name='test.jpg')
        self.category = Category.objects.create(name="Test Category")
        self.product = Product.objects.create(name="Test Product",
                                              category=self.category)
        self.user = User.objects.create(email="test@example.com")

    @patch('backend.signals.generate_product_thumbnails.delay')
    def test_process_product_image_on_save_new_product(self, mock_delay):
        """
        Тест обработки нового изображения товара при сохранении:
        - Добавляем изображение к товару
        - Сохраняем товар
        - Проверяем что задача на генерацию уменьшенных копий была вызвана
        """

        self.product.image = self.image_file
        self.product.save()
        mock_delay.assert_called_once_with(self.product.id,
                                           [(400, 400), (200, 200), (100, 100)])

    @patch('backend.signals.generate_product_thumbnails.delay')
    def test_process_product_image_on_save_image_changed(self, mock_delay):
        """
        Тест обработки изменения изображения товара:
        - Сохраняем товар с первым изображением
        - Создаем второе тестовое изображение
        - Меняем изображение товара на новое
        - Сохраняем товар
        - Проверяем что задача вызывалась дважды (по разу для каждого изображения)
        """
        self.product.image = self.image_file
        self.product.save()

        image2 = Image.new('RGB', (1000, 1000), color='blue')
        image_file2 = BytesIO()
        image2.save(image_file2, 'JPEG')
        image_file2.seek(0)
        image_file2 = File(image_file2, name='test2.jpg')

        self.product.image = image_file2
        self.product.save()
        self.assertEqual(mock_delay.call_count, 2)

    @patch('backend.signals.generate_user_thumbnails.delay')
    def test_process_user_avatar_on_save_new_avatar(self, mock_delay):
        """
        Тест обработки нового аватара пользователя при сохранении:
        - Добавляем аватар пользователю
        - Сохраняем пользователя
        - Проверяем что задача на генерацию уменьшенных копий была вызвана
        """

        self.user.avatar = self.image_file
        self.user.save()
        mock_delay.assert_called_once_with(user_id=self.user.id,
                                           sizes=[(200, 200), (100, 100), (50, 50)])

    @patch('backend.signals.generate_user_thumbnails.delay')
    def test_process_user_avatar_on_save_avatar_changed(self, mock_delay):
        """
        Тест обработки изменения аватара пользователя:
        - Сохраняем пользователя с первым аватаром
        - Создаем второе тестовое изображение
        - Меняем аватар пользователя на новое
        - Сохраняем пользователя
        - Проверяем что задача вызывалась дважды (по разу для каждого аватара)
        """
        self.user.avatar = self.image_file
        self.user.save()

        image2 = Image.new('RGB', (1000, 1000), color='blue')
        image_file2 = BytesIO()
        image2.save(image_file2, 'JPEG')
        image_file2.seek(0)
        image_file2 = File(image_file2, name='test2.jpg')

        self.user.avatar = image_file2
        self.user.save()
        self.assertEqual(mock_delay.call_count, 2)

    @patch('backend.signals.generate_user_thumbnails.delay')
    def test_process_user_avatar_on_save_no_avatar(self, mock_delay):
        """
        Тест обработки сохранения пользователя без аватара:
        - Сохраняем пользователя без изменения аватара
        - Проверяем что задача на генерацию уменьшенных копий не вызывалась
        """

        self.user.save()
        mock_delay.assert_not_called()
