import os
import django
from django.core.cache import cache
from django.test import TestCase

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'orders.settings')
django.setup()


class RedisConnectionTest(TestCase):

    def setUp(self):
        cache.clear()

    def test_redis_connection(self):
        cache.set('test_key', 'test_value', timeout=60)
        value = cache.get('test_key')
        self.assertEqual(value, 'test_value')

    def test_cacheops_key_pattern(self):
        cache.set('cacheops:test', 'cacheops_value', timeout=30)
        cacheops_value = cache.get('cacheops:test')
        self.assertEqual(cacheops_value, 'cacheops_value')
