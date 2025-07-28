import json

from backend.models import Category, Shop, Product, ProductInfo, OrderItem, Order
from rest_framework.test import APITestCase, APIClient
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model
from django.urls import reverse


User = get_user_model()


class BasketViewTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('backend:basket')
        self.user = User.objects.create_user(email='user@example.com',
                                             password='testpassword',
                                             is_active=True)
        self.token = Token.objects.create(user=self.user)
        self.category = Category.objects.create(name='Test Category')
        self.shop = Shop.objects.create(name='Test Shop', state=True)
        self.product = Product.objects.create(name='Test Product', category=self.category)
        self.product_info = ProductInfo.objects.create(product=self.product,
                                                       shop=self.shop,
                                                       external_id=12345,
                                                       price=100,
                                                       price_rrc=120,
                                                       quantity=10)

    def test_get_basket_authenticated(self):
        """Позитивный тест: получение корзины авторизованного пользователя"""

        order = Order.objects.create(user=self.user, state='basket')
        OrderItem.objects.create(order=order, product_info=self.product_info, quantity=1)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    def test_get_basket_unauthenticated(self):
        """Негативный тест: попытка получить корзину без авторизации"""

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['Error'], 'Требуется авторизация.')

    def test_add_to_basket_valid_items(self):
        """Позитивный тест: добавление товаров в корзину"""

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        items = [{'product_info': self.product_info.id, 'quantity': 2}]
        response = self.client.post(self.url,
                                    data={'items': json.dumps(items)},
                                    format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()['Status'])
        self.assertEqual(response.json()['Создано объектов'], 1)

    def test_add_to_basket_invalid_items(self):
        """Негативный тест: добавление невалидных данных в корзину"""

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        response = self.client.post(self.url,
                                    data={'items': 'invalid_json'},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['Status'])
        self.assertEqual(response.json()['Errors'], 'Неверный формат запроса')

    def test_update_basket_item_put(self):
        """Позитивный тест: обновление количества товара в корзине"""

        order = Order.objects.create(user=self.user, state='basket')
        order_item = OrderItem.objects.create(order=order,
                                              product_info=self.product_info,
                                              quantity=1)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        items = [{'id': order_item.id, 'quantity': 5}]
        response = self.client.put(self.url,
                                   data={'items': json.dumps(items)},
                                   format='json')
        self.assertEqual(response.status_code, 200)
        order_item.refresh_from_db()
        self.assertEqual(order_item.quantity, 5)
        self.assertEqual(response.json()['Обновлено объектов'], 1)

    def test_delete_basket_item(self):
        """Позитивный тест: удаление товара из корзины"""

        order = Order.objects.create(user=self.user, state='basket')
        order_item = OrderItem.objects.create(order=order,
                                              product_info=self.product_info,
                                              quantity=1)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        response = self.client.delete(self.url,
                                      data={'items': str(order_item.id)},
                                      format='json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(OrderItem.objects.filter(id=order_item.id).exists())
