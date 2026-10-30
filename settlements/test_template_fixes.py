from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from settlements.models import Holiday


class TemplateFixTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("u", password="x")
        self.client.force_login(self.user)

    def test_holiday_edit_button_passes_the_name(self):
        holiday = Holiday.objects.create(name="Dia Teste", date=date(2026, 12, 26))
        response = self.client.get(reverse("holiday-list"))
        self.assertContains(
            response, f'openEdit({holiday.pk}, "Dia Teste", "2026-12-26"',
        )

    def test_delivery_report_route_is_gone(self):
        with self.assertRaises(NoReverseMatch):
            reverse("driver-delivery-report", args=[1])
