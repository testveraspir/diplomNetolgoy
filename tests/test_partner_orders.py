from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model
from django.db.models import Sum, F
from backend.models import Shop, Category, Product, ProductInfo, Order, OrderItem, Contact


User = get_user_model()


class PartnerOrdersTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('backend:partner-orders')
        self.shop_user = User.objects.create_user(email='shop@example.com',
                                                  password='testpassword',
                                                  is_active=True,
                                                  type='shop')
        self.shop_token = Token.objects.create(user=self.shop_user)
        self.regular_user = User.objects.create_user(email='user@example.com',
                                                     password='testpassword',
                                                     is_active=True,
                                                     type='buyer')
        self.regular_token = Token.objects.create(user=self.regular_user)

        self.shop = Shop.objects.create(name='Test Shop', user=self.shop_user, state=True)
        self.category = Category.objects.create(name='Test Category')
        self.product = Product.objects.create(name='Test Product', category=self.category)
        self.product_info = ProductInfo.objects.create(product=self.product,
                                                       shop=self.shop,
                                                       external_id=12345,
                                                       price=100,
                                                       price_rrc=120,
                                                       quantity=10)

        self.contact = Contact.objects.create(user=self.regular_user,
                                              city='Test City',
                                              street='Test Street',
                                              phone='+1234567890')

        self.order = Order.objects.create(user=self.regular_user, state='new', contact=self.contact)

        OrderItem.objects.create(order=self.order, product_info=self.product_info, quantity=2)

    def test_get_orders_as_shop(self):
        """Позитивный тест: получение заказов"""

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.shop_token.key)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        expected_total = OrderItem.objects.filter(
            order=self.order).aggregate(total=Sum(F('quantity') * F('product_info__price')))['total']
        self.assertEqual(float(response.data[0]['total_sum']), float(expected_total))

    def test_get_orders_unauthenticated(self):
        """Негативный тест: неавторизованный пользователь"""

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['Error'], 'Требуется авторизация.')

    def test_get_orders_as_regular_user(self):
        """Негативный тест: попытка получить заказ не магазином"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.regular_token.key)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['Error'], 'Только для магазинов')

    def test_no_orders_for_shop(self):
        """Позитивный тест: магазин без заказов"""

        new_shop_user = User.objects.create_user(email='newshop@example.com',
                                                 password='testpassword',
                                                 is_active=True,
                                                 type='shop')
        new_shop_token = Token.objects.create(user=new_shop_user)
        Shop.objects.create(name='Empty Shop', user=new_shop_user, state=True)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + new_shop_token.key)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_exclude_basket_orders(self):
        """Позитивный тест: корзины не включаются в результаты"""

        basket_order = Order.objects.create(user=self.regular_user,
                                            state='basket',
                                            contact=self.contact)
        OrderItem.objects.create(order=basket_order,
                                 product_info=self.product_info,
                                 quantity=1)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.shop_token.key)
        response = self.client.get(self.url)
        self.assertEqual(len(response.data), 1)
        self.assertNotEqual(response.data[0]['id'], basket_order.id)

    def test_order_serializer_fields(self):
        """Позитивный тест: проверка наличия основных полей в ответе"""

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.shop_token.key)
        response = self.client.get(self.url)
        order_data = response.data[0]
        self.assertIn('id', order_data)
        self.assertIn('state', order_data)
        self.assertIn('dt', order_data)
        self.assertIn('total_sum', order_data)
        self.assertIn('contact', order_data)
        self.assertIn('ordered_items', order_data)

        item = order_data['ordered_items'][0]
        self.assertIn('product_info', item)
        self.assertIn('quantity', item)

        product_info = item['product_info']
        self.assertIn('product', product_info)
        self.assertIn('price', product_info)

        product = product_info['product']
        self.assertIn('name', product)
        self.assertIn('category', product)
