"""
Tests for the opportunity analytics endpoints.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from deals.models import Deal
from customers.models import Customer

User = get_user_model()


class OpportunityAuthTests(APITestCase):
    """All opportunity endpoints must require authentication."""

    def test_statistics_requires_auth(self):
        response = self.client.get(reverse("opportunity-statistics"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_summary_requires_auth(self):
        response = self.client.get(reverse("opportunity-summary"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_filters_requires_auth(self):
        response = self.client.get(reverse("opportunity-filters"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customers_dropdown_requires_auth(self):
        response = self.client.get(reverse("opportunity-customers-dropdown"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_companies_dropdown_requires_auth(self):
        response = self.client.get(reverse("opportunity-companies-dropdown"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class OpportunityPlaceholderTests(APITestCase):
    """When no Deal/Customer records exist, endpoints should return placeholder data."""

    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="testpass123")
        self.client.force_authenticate(user=self.user)

    def test_statistics_placeholder(self):
        response = self.client.get(reverse("opportunity-statistics"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_opportunities"], 15)
        self.assertEqual(response.data["active_opportunities"], 10)
        self.assertEqual(response.data["closed_won"], 2)
        self.assertEqual(Decimal(response.data["pipeline_value"]), Decimal("1473000.00"))
        self.assertEqual(response.data["average_probability"], 55)

    def test_summary_placeholder(self):
        response = self.client.get(reverse("opportunity-summary"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_opportunities"], 15)

    def test_filters_placeholder(self):
        response = self.client.get(reverse("opportunity-filters"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_records"], 15)
        self.assertEqual(len(response.data["stages"]), 6)
        stage_values = [item["value"] for item in response.data["stages"]]
        self.assertIn("closed_won", stage_values)
        self.assertIn("closed_lost", stage_values)

    def test_customers_dropdown_placeholder(self):
        response = self.client.get(reverse("opportunity-customers-dropdown"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["name"], "Sarah Khan")

    def test_companies_dropdown_placeholder(self):
        response = self.client.get(reverse("opportunity-companies-dropdown"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)


class OpportunityRealDataTests(APITestCase):
    """When Deal/Customer records exist, endpoints should aggregate real data instead of placeholders."""

    def setUp(self):
        self.user = User.objects.create_user(username="tester2", password="testpass123")
        self.client.force_authenticate(user=self.user)

        self.customer1 = Customer.objects.create(
            first_name="Sarah", last_name="Khan",
            email="sarah@example.com", phone="123",
            company="Global Solutions",
        )
        self.customer2 = Customer.objects.create(
            first_name="Ali", last_name="Raza",
            email="ali@example.com", phone="456",
            company="Innovatech Ltd",
        )

        today = date.today()

        # Two active deals, one closed_won, one closed_lost -> total 4
        Deal.objects.create(
            name="Deal A", customer=self.customer1, value=Decimal("1000.00"),
            stage="qualified", expected_close_date=today + timedelta(days=30),
            probability=40,
        )
        Deal.objects.create(
            name="Deal B", customer=self.customer1, value=Decimal("2000.00"),
            stage="proposal", expected_close_date=today + timedelta(days=15),
            probability=60,
        )
        Deal.objects.create(
            name="Deal C", customer=self.customer2, value=Decimal("3000.00"),
            stage="closed_won", expected_close_date=today,
            probability=100,
        )
        Deal.objects.create(
            name="Deal D", customer=self.customer2, value=Decimal("500.00"),
            stage="closed_lost", expected_close_date=today,
            probability=0,
        )

    def test_statistics_uses_real_data(self):
        response = self.client.get(reverse("opportunity-statistics"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_opportunities"], 4)
        self.assertEqual(response.data["active_opportunities"], 2)  # qualified + proposal
        self.assertEqual(response.data["closed_won"], 1)
        self.assertEqual(Decimal(response.data["pipeline_value"]), Decimal("6500.00"))
        self.assertEqual(response.data["average_probability"], 50)  # (40+60+100+0)/4

    def test_summary_uses_real_data(self):
        response = self.client.get(reverse("opportunity-summary"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_opportunities"], 4)
        self.assertEqual(response.data["closed_won"], 1)

    def test_filters_uses_real_data(self):
        response = self.client.get(reverse("opportunity-filters"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_records"], 4)

    def test_customers_dropdown_uses_real_data(self):
        response = self.client.get(reverse("opportunity-customers-dropdown"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        names = [item["name"] for item in response.data]
        self.assertIn("Ali Raza", names)
        self.assertIn("Sarah Khan", names)

    def test_companies_dropdown_uses_real_data(self):
        response = self.client.get(reverse("opportunity-companies-dropdown"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        companies = [item["company"] for item in response.data]
        self.assertIn("Global Solutions", companies)
        self.assertIn("Innovatech Ltd", companies)