from rest_framework.test import APITestCase, APIClient
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model
from backend.models import ConfirmEmailToken, Contact
from django.urls import reverse
from django.core.cache import cache


User = get_user_model()


class RegisterAccountTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = reverse('backend:user-register')
        self.valid_data = {'first_name': 'John',
                           'last_name': 'Doe',
                           'email': 'john@example.com',
                           'password': 'securepassword123',
                           'company': 'Test Company',
                           'position': 'Manager'}

    def test_register_valid_data(self):
        """Позитивный тест: регистрация с валидными данными"""

        response = self.client.post(self.url, self.valid_data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()['Status'])
        self.assertTrue(User.objects.filter(email=self.valid_data['email']).exists())

    def test_register_missing_fields(self):
        """Негативный тест: отсутствие обязательных полей"""

        invalid_data = self.valid_data.copy()
        del invalid_data['email']
        response = self.client.post(self.url, invalid_data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['Errors'], 'Необходимые поля отсутствуют.')

    def test_register_weak_password(self):
        """Негативный тест: слабый пароль"""

        weak_password_data = self.valid_data.copy()
        weak_password_data['password'] = '123'
        response = self.client.post(self.url, weak_password_data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('password', response.json()['Errors'])


class ConfirmAccountTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('backend:user-register-confirm')
        self.user = User.objects.create_user(email='unconfirmed@example.com',
                                             password='password',
                                             is_active=False)
        self.token = ConfirmEmailToken.objects.create(user=self.user, key='testtoken')

    def test_confirm_valid_token(self):
        """Позитивный тест: подтверждение с валидным токеном"""

        data = {'email': 'unconfirmed@example.com', 'token': 'testtoken'}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['Status'])
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_confirm_invalid_token(self):
        """Негативный тест: неверный токен"""

        data = {'email': 'unconfirmed@example.com', 'token': 'wrongtoken'}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['Errors'], 'Неправильно указан токен или email')

    def test_confirm_missing_fields(self):
        """Негативный тест: отсутствие обязательных полей"""

        response = self.client.post(self.url, {'email': 'unconfirmed@example.com'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['Errors'], 'Необходимые поля отсутствуют.')


class LoginAccountTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('backend:user-login')
        self.user = User.objects.create_user(email='test@example.com',
                                             password='testpassword',
                                             is_active=True)

    def test_login_valid_credentials(self):
        """Позитивный тест: успешная авторизация"""

        data = {'email': 'test@example.com', 'password': 'testpassword'}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['Status'])
        self.assertIn('Token', response.json())

    def test_login_invalid_password(self):
        """Негативный тест: неверный пароль"""

        data = {'email': 'test@example.com', 'password': 'wrongpassword'}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['Errors'], 'Не удалось авторизовать')

    def test_login_missing_fields(self):
        """Негативный тест: отсутствие обязательных полей"""

        response = self.client.post(self.url, {'email': 'test@example.com'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['Errors'], 'Необходимые поля отсутствуют.')


class AccountDetailsTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('backend:user-details')
        self.user = User.objects.create_user(email='test@example.com',
                                             password='testpassword',
                                             first_name='John',
                                             last_name='Doe',
                                             is_active=True)
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)

    def test_get_details_authenticated(self):
        """Позитивный тест: получение данных авторизованного пользователя"""

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['email'], 'test@example.com')

    def test_get_details_unauthenticated(self):
        """Негативный тест: попытка получить данные без авторизации"""

        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['Error'], 'Требуется авторизация.')

    def test_update_details_valid_data(self):
        """Позитивный тест: обновление данных пользователя"""

        data = {'first_name': 'Bob', 'last_name': 'Ivanov'}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Bob')
        self.assertEqual(self.user.last_name, 'Ivanov')

    def test_update_password_valid(self):
        """Позитивный тест: обновление пароля"""

        data = {'password': 'newsecurepassword123'}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newsecurepassword123'))

    def test_invalid_method_put(self):
        """Негативный тест: попытка использовать метод PUT"""

        data = {'first_name': 'Bob', 'last_name': 'Ivanov'}
        response = self.client.put(self.url, data, format='json')
        self.assertEqual(response.status_code, 405)


class ContactViewTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('backend:user-contact')
        self.user = User.objects.create_user(email='user@example.com',
                                             password='testpassword',
                                             is_active=True)
        self.contact = Contact.objects.create(user=self.user,
                                              city='Initial City',
                                              street='Initial Street',
                                              phone='+79000000000')
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)

    def test_get_contacts_authenticated(self):
        """Позитивный тест: получение контактов пользователя"""

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_get_contacts_unauthenticated(self):
        """Негативный тест: получение контактов неавторизованного пользователя"""

        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['Error'], 'Требуется авторизация.')

    def test_add_contact_valid_data(self):
        """Позитивный тест: добавление нового контакта"""

        data = {
            'city': 'Test City',
            'street': 'Test Street',
            'phone': '+1234567890'
        }
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Contact.objects.count(), 2)

    def test_add_contact_missing_fields(self):
        """Негативный тест: отсутствие обязательных полей"""

        response = self.client.post(self.url, {'city': 'Test City'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['Errors'], 'Необходимые поля отсутствуют.')

    def test_update_contact_put(self):
        """Позитивный тест: обновление контакта"""

        data = {
            'city': 'Updated City',
            'street': 'Updated Street',
            'phone': '+79111111111',
            'id': str(self.contact.id)
        }
        response = self.client.put(self.url, data, format='json')
        self.assertEqual(response.status_code, 200)
        self.contact.refresh_from_db()
        self.assertEqual(self.contact.city, 'Updated City')

    def test_delete_contact(self):
        """Позитивный тест: удаление контакта"""

        items = f"{self.contact.id}"
        response = self.client.delete(self.url, data={'items': items}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['Удалено объектов'], 1)
        self.assertFalse(Contact.objects.filter(id=self.contact.id).exists())

    def test_delete_contacts_unauthenticated(self):
        """Негативный тест: попытка удаления без авторизации"""

        self.client.credentials()
        response = self.client.delete(self.url, data={'items': '1'}, format='json')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['Error'], 'Требуется авторизация.')

    def test_delete_contacts_without_items(self):
        """Негативный тест: попытка удаления без items"""

        response = self.client.delete(self.url, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['Errors'], 'Необходимые поля отсутствуют.')

    def test_delete_contacts_invalid_items(self):
        """Негативный тест: попытка удаления c некорректным items"""

        response = self.client.delete(self.url, data={'items': 'abc,def'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['Status'], False)

    def test_delete_nonexistent_contacts(self):
        """Негативный тест: попытка удаления несуществующих контактов"""

        nonexistent_id = 99999
        response = self.client.delete(self.url, data={'items': str(nonexistent_id)}, format='json')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['Error'], 'Контакты не найдены')
