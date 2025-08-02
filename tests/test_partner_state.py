from rest_framework.test import APITestCase, APIClient
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model
from django.urls import reverse
from backend.models import Shop


User = get_user_model()


class PartnerStateTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('backend:partner-state')
        self.user = User.objects.create_user(email='partner@example.com',
                                             password='testpassword',
                                             is_active=True,
                                             type='shop')
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        self.shop = Shop.objects.create(name='Test Shop', user=self.user)

    def test_get_current_shop_state(self):
        """ Позитивный тест: получение текущего статуса магазина"""

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.json()
        self.assertIn('state', content)
        self.assertEqual(self.shop.state, True)

    def test_change_shop_state_post(self):
        """ Позитивный тест: изменение статуса магазина"""

        old_state = self.shop.state
        new_state = not old_state
        data = {'state': new_state}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 200)
        self.shop.refresh_from_db()
        self.assertEqual(self.shop.state, new_state)

    def test_get_without_authorization(self):
        """ Негативный тест: попытка GET-запроса без авторизации"""

        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['Error'], 'Требуется авторизация.')

    def test_post_without_authorization(self):
        """ Негативный тест: попытка POST-запроса без авторизации"""

        self.client.credentials()
        data = {'state': True}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['Error'], 'Требуется авторизация.')

    def test_invalid_user_type(self):
        """ Негативный тест: неправильный тип пользователя"""

        self.user.type = 'buyer'
        self.user.save()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['Error'], 'Только для магазинов')

    def test_missing_required_field_in_post(self):
        """ Негативный тест: отсутствие обязательного поля в POST-запросе"""

        data = {}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get('Errors'), 'Поле "state" отсутствует.')

    def test_update_shop_state_put(self):
        """Негативный тест: попытка использования метода put"""

        data = {'state': False}
        response = self.client.put(self.url, data, format='json')
        self.assertEqual(response.status_code, 405)
        self.shop.refresh_from_db()
