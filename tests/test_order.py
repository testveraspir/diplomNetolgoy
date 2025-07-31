from backend.models import Contact, Order
from rest_framework.test import APITestCase, APIClient
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model
from django.urls import reverse


User = get_user_model()


class OrderViewTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('backend:order')
        self.user = User.objects.create_user(email='user@example.com',
                                             password='testpassword',
                                             is_active=True)
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)

        self.contact = Contact.objects.create(user=self.user,
                                              city='Test City',
                                              street='Test Street',
                                              phone='+1234567890')
        self.order = Order.objects.create(user=self.user, state='basket')

    def test_get_orders_authenticated(self):
        """Позитивный тест: получение списка заказов"""

        Order.objects.create(user=self.user, state='new')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_create_order_valid_data(self):
        """Позитивный тест: оформление заказа из корзины"""

        response = self.client.post(self.url,
                                    {'id': str(self.order.id), 'contact': str(self.contact.id)},
                                    format='json')
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.state, 'new')

    def test_create_order_missing_fields(self):
        """Негативный тест: отсутствие обязательных полей"""

        response = self.client.post(self.url, {'id': self.order.id}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['Errors'], 'Необходимые поля отсутствуют.')
