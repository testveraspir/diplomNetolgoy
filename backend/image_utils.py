from io import BytesIO
from PIL import Image
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile


def generate_and_save_thumbnails(instance, image_field_name, thumbnails_field_name, sizes):
    """
    Универсальная функция для генерации миниатюр

    :param instance: Объект модели (Product или User)
    :param image_field_name: Имя поля с оригинальным изображением
    :param thumbnails_field_name: Имя поля для хранения путей миниатюр
    :param sizes: Список размеров [(width, height), ...]
    :return: Словарь с путями миниатюр
    """

    original_image = getattr(instance, image_field_name)
    if not original_image:
        return {}

    thumbnails = {}

    try:
        img = Image.open(original_image.path)

        for width, height in sizes:
            try:
                # Генерация имени файла: размер_оригинальное_имя
                filename = f'{width}x{height}_{original_image.name.split("/")[-1]}'
                thumbnail_path = f'{image_field_name}/thumbnails/{instance.id}/{filename}'

                if default_storage.exists(thumbnail_path):
                    thumbnails[f'{width}x{height}'] = thumbnail_path
                    continue

                # Обработка изображения
                img_copy = img.copy()
                img_copy.thumbnail((width, height))

                # Сохранение в буфер
                buffer = BytesIO()
                img_copy.save(buffer, format='JPEG', quality=85, optimize=True)
                buffer.seek(0)

                # Сохранение миниатюры
                default_storage.save(thumbnail_path, ContentFile(buffer.getvalue()))
                thumbnails[f'{width}x{height}'] = thumbnail_path

            except Exception:
                continue

        print(f"Original image path: {original_image.path}")
        print(f"Image exists: {default_storage.exists(original_image.path)}")

        # Обновление модели
        update_data = {thumbnails_field_name: thumbnails}
        instance.__class__.objects.filter(id=instance.id).update(**update_data)

        return thumbnails
    except Exception:
        return {}
