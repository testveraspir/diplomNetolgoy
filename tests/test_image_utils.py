from io import BytesIO
from unittest.mock import Mock, patch
from PIL import Image
from django.core.files.base import ContentFile
from django.test import TestCase

from backend.image_utils import generate_and_save_thumbnails


class GenerateAndSaveThumbnailsTestCase(TestCase):
    """Тесты для функции generate_and_save_thumbnails."""

    def setUp(self):
        """Настройка тестовых данных"""
        self.mock_instance = Mock()
        self.mock_instance.id = 1
        self.mock_instance.__class__.objects = Mock()

        # Создание временного изображение для тестов
        self.test_image = Image.new('RGB', (100, 100), color='red')
        self.buffer = BytesIO()
        self.test_image.save(self.buffer, format='JPEG')
        self.buffer.seek(0)

    def tearDown(self):
        """Очистка после тестов"""
        if hasattr(self, 'buffer'):
            self.buffer.close()

    @patch('backend.image_utils.default_storage')
    @patch('backend.image_utils.Image.open')
    def test_generate_thumbnails_success(self, mock_image_open, mock_storage):
        """Тест успешной генерации миниатюр"""

        mock_image = Mock()
        mock_image.copy.return_value = mock_image
        mock_image_open.return_value = mock_image

        mock_storage.exists.return_value = False
        mock_storage.save.return_value = 'test_path.jpg'

        mock_image_field = Mock()
        mock_image_field.name = 'test_image.jpg'
        mock_image_field.path = '/path/to/test_image.jpg'
        getattr(self.mock_instance, 'image_field').return_value = mock_image_field
        self.mock_instance.image_field = mock_image_field

        sizes = [(50, 50), (25, 25)]

        result = generate_and_save_thumbnails(self.mock_instance,
                                              'image_field',
                                              'thumbnails_field',
                                              sizes)

        self.assertEqual(len(result), 2)
        self.assertIn('50x50', result)
        self.assertIn('25x25', result)

        self.assertEqual(mock_storage.save.call_count, 2)
        mock_storage.exists.assert_called()
        self.mock_instance.__class__.objects.filter().update.assert_called_once()

    @patch('backend.image_utils.default_storage')
    def test_no_original_image(self, mock_storage):
        """Тест, когда оригинальное изображение отсутствует"""

        mock_image_field = Mock()
        mock_image_field.__bool__ = Mock(return_value=False)
        self.mock_instance.image_field = mock_image_field

        result = generate_and_save_thumbnails(self.mock_instance,
                                              'image_field',
                                              'thumbnails_field',
                                              [(50, 50)])

        self.assertEqual(result, {})
        mock_storage.save.assert_not_called()

    @patch('backend.image_utils.default_storage')
    @patch('backend.image_utils.Image.open')
    def test_thumbnails_already_exist(self, mock_image_open, mock_storage):
        """Тест, когда миниатюры уже существуют"""

        mock_image = Mock()
        mock_image_open.return_value = mock_image

        mock_image_field = Mock()
        mock_image_field.name = 'test_image.jpg'
        mock_image_field.path = '/path/to/test_image.jpg'
        self.mock_instance.image_field = mock_image_field

        mock_storage.exists.return_value = True

        sizes = [(50, 50)]

        result = generate_and_save_thumbnails(self.mock_instance,
                                              'image_field',
                                              'thumbnails_field',
                                              sizes)

        self.assertEqual(len(result), 1)
        mock_storage.save.assert_not_called()
        mock_storage.exists.assert_called()

    @patch('backend.image_utils.default_storage')
    @patch('backend.image_utils.Image.open')
    def test_image_processing_exception(self, mock_image_open, mock_storage):
        """Тест обработки исключения при обработке изображения"""

        mock_image = Mock()
        mock_image.copy.side_effect = Exception('Processing error')
        mock_image_open.return_value = mock_image

        mock_image_field = Mock()
        mock_image_field.name = 'test_image.jpg'
        mock_image_field.path = '/path/to/test_image.jpg'
        self.mock_instance.image_field = mock_image_field

        mock_storage.exists.return_value = False

        sizes = [(50, 50)]

        result = generate_and_save_thumbnails(self.mock_instance,
                                              'image_field',
                                              'thumbnails_field',
                                              sizes)
        self.assertEqual(result, {})

    @patch('backend.image_utils.default_storage')
    @patch('backend.image_utils.Image.open')
    def test_general_exception_handling(self, mock_image_open, mock_storage):
        """Тест обработки общего исключения"""

        mock_image_open.side_effect = Exception('General error')

        mock_image_field = Mock()
        mock_image_field.name = 'test_image.jpg'
        mock_image_field.path = '/path/to/test_image.jpg'
        self.mock_instance.image_field = mock_image_field

        result = generate_and_save_thumbnails(self.mock_instance,
                                              'image_field',
                                              'thumbnails_field',
                                              [(50, 50)])

        self.assertEqual(result, {})

    @patch('backend.image_utils.default_storage')
    @patch('backend.image_utils.Image.open')
    def test_thumbnail_generation_quality(self, mock_image_open, mock_storage):
        """Тест проверки качества генерации миниатюр"""

        mock_image = Mock()
        mock_image.copy.return_value = mock_image
        mock_image_open.return_value = mock_image

        mock_storage.exists.return_value = False

        mock_image_field = Mock()
        mock_image_field.name = 'test_image.jpg'
        mock_image_field.path = '/path/to/test_image.jpg'
        self.mock_instance.image_field = mock_image_field

        sizes = [(50, 50)]

        generate_and_save_thumbnails(self.mock_instance,
                                     'image_field',
                                     'thumbnails_field',
                                     sizes)

        mock_storage.save.assert_called_once()
        args, kwargs = mock_storage.save.call_args
        self.assertTrue(isinstance(args[1], ContentFile))

    @patch('backend.image_utils.default_storage')
    @patch('backend.image_utils.Image.open')
    def test_multiple_sizes_processing(self, mock_image_open, mock_storage):
        """Тест обработки нескольких размеров"""

        mock_image = Mock()
        mock_image.copy.return_value = mock_image
        mock_image_open.return_value = mock_image

        mock_storage.exists.return_value = False
        mock_storage.save.return_value = 'test_path.jpg'

        mock_image_field = Mock()
        mock_image_field.name = 'test_image.jpg'
        mock_image_field.path = '/path/to/test_image.jpg'
        self.mock_instance.image_field = mock_image_field

        sizes = [(100, 100), (50, 50), (25, 25)]

        result = generate_and_save_thumbnails(self.mock_instance,
                                              'image_field',
                                              'thumbnails_field',
                                              sizes)

        self.assertEqual(len(result), 3)
        self.assertEqual(mock_storage.save.call_count, 3)
