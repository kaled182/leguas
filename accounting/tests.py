from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse




class BreakEvenTemplateTests(TestCase):
    def test_script_number_uses_a_dot(self):
        user = User.objects.create_superuser("be", password="x")
        self.client.force_login(user)
        response = self.client.get(reverse("accounting:break_even"))
        self.assertRegex(
            response.content.decode(), r"const COST_FIXED = -?\d+\.\d{2};",
        )
