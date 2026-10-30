# Tests para fleet_management

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Vehicle, VehicleIncident


class IncidentListTests(TestCase):
    def test_list_renders_with_an_incident(self):
        user = User.objects.create_user("u", password="x", is_staff=True)
        self.client.force_login(user)
        vehicle = Vehicle.objects.create(
            license_plate="AA-00-AA", brand="Marca", model="Modelo", year=2024,
        )
        VehicleIncident.objects.create(
            vehicle=vehicle, incident_type="MULTA", description="Teste",
            incident_date=date(2026, 10, 30),
        )

        response = self.client.get(reverse("fleet:incident_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "30/10/2026")
