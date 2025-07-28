import os
import responses
from rest_framework.test import APITestCase, APIClient
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model
from django.urls import reverse
from unittest.mock import patch


User = get_user_model()


class PartnerUpdateTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('backend:partner-update')
        self.user = User.objects.create_user(email='partner@example.com',
                                             password='testpassword',
                                             is_active=True,
                                             type='shop')
        self.file_path = os.path.join(os.path.dirname(__file__), 'test_price.yaml')
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)

    @responses.activate
    def test_partner_update_valid_url(self):
        """Позитивный тест: обновление прайса по валидному URL"""

        with open(self.file_path, 'r', encoding='utf-8') as file:
            content = file.read()

        responses.add(responses.GET, 'http://example.com/price.yaml',
                      body=content, status=200, content_type='text/yaml')

        response = self.client.post(self.url, {'url': 'http://example.com/price.yaml'}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['Status'])
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(responses.calls[0].request.url, 'http://example.com/price.yaml')

    def test_partner_update_unauthenticated(self):
        """Негативный тест: попытка обновить без авторизации"""

        self.client.credentials()
        response = self.client.post(self.url, {'url': 'http://example.com/price.yaml'}, format='json')
        self.assertEqual(response.status_code, 401)

    def test_partner_update_not_partner(self):
        """Негативный тест: попытка обновить не магазином"""

        regular_user = User.objects.create_user(email='regular@example.com',
                                                password='testpassword',
                                                is_active=True,
                                                type='buyer')
        token = Token.objects.create(user=regular_user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        response = self.client.post(self.url, {'url': 'http://example.com/price.yaml'}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_partner_update_invalid_url(self):
        """Негативный тест: невалидный URL"""

        response = self.client.post(self.url, {'url': 'invalid_url'}, format='json')
        self.assertEqual(response.status_code, 400)
