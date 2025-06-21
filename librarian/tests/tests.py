from django.test import TestCase

# Create your tests here.

from django.test import TestCase
from django.contrib.auth import get_user_model

class UserTests(TestCase):
    def test_create_user(self):
        user = get_user_model().objects.create_user(
            username='testuser',
            password='testpass123',
        )
        self.assertEqual(user.username, 'testuser')
