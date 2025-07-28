from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from django.contrib.auth import get_user_model
from backend.models import Shop, Category, Product, ProductInfo


User = get_user_model()


class ProductInfoViewTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('backend:products')
        self.category = Category.objects.create(name='Test Category')
        self.shop = Shop.objects.create(name='Test Shop', state=True)
        self.product = Product.objects.create(name='Test Product', category=self.category)
        self.product_info = ProductInfo.objects.create(product=self.product,
                                                       shop=self.shop,
                                                       external_id=12345,
                                                       price=100,
                                                       price_rrc=120,
                                                       quantity=10)

    def test_filter_by_category(self):
        """Позитивный тест: фильтрации по категории"""

        response = self.client.get(f'{self.url}?category_id={self.category.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.product_info.id)

    def test_filter_by_shop(self):
        """Позитивный тест: фильтрации по магазину"""

        response = self.client.get(f'{self.url}?shop_id={self.shop.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
