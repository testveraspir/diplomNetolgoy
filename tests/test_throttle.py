from django.urls import reverse
from rest_framework.test import APITestCase


class RegisterAccountThrottleTest(APITestCase):
    def setUp(self):
        self.url = reverse('backend:user-register')
        self.data = {
            'first_name': 'User',
            'last_name': 'User',
            'email': 'test{id}@example.com',
            'password': 'SecurePass123!',
            'company': 'Test Inc',
            'position': 'Manager'
        }

    def test_anon_throttling(self):

        for i in range(5):
            data = self.data.copy()
            data['email'] = f'test{i}@example.com'
            response = self.client.post(self.url, data)
            self.assertIn(response.status_code, [201, 400])

        response = self.client.post(self.url, self.data)
        self.assertEqual(response.status_code, 429)
