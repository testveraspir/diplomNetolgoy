from django.test import TestCase
from django.db import connection
from django.core.cache import cache
from backend.models import ProductInfo


class CacheopsVerificationTest(TestCase):

    def setUp(self):
        cache.clear()

    def test_query_from_cache(self):
        """Проверка, что второй запрос идет из кэша, а не из БД"""

        # Первый запрос - должен сделать 1 SQL запрос
        with self.assertNumQueries(1):
            result1 = list(ProductInfo.objects.all())

        # Второй запрос - должен сделать 0 SQL запросов (из кэша)
        with self.assertNumQueries(0):
            result2 = list(ProductInfo.objects.all())

        # Проверяем что данные идентичны
        self.assertEqual(len(result1), len(result2))
        self.assertEqual(
            [item.id for item in result1],
            [item.id for item in result2]
        )
