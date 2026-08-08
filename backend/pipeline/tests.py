"""
Tests for the pipeline analytics endpoints.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from dashboard.models import Deal
from customers.models import Customer

User = get_user_model()


class PipelineAuthTests(APITestCase):
    """All pipeline endpoints must require authentication."""

    def test_summary_requires_auth(self):
        response = self.client.get(reverse("pipeline-summary"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_stages_requires_auth(self):
        response = self.client.get(reverse("pipeline-stages"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_recent_deals_requires_auth(self):
        response = self.client.get(reverse("pipeline-recent-deals"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_performance_requires_auth(self):
        response = self.client.get(reverse("pipeline-performance"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PipelinePlaceholderTests(APITestCase):
    """When no Deal objects exist, endpoints should return placeholder data."""

    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="testpass123")
        self.client.force_authenticate(user=self.user)

    def test_summary_placeholder(self):
        response = self.client.get(reverse("pipeline-summary"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_deals"], 42)
        self.assertEqual(Decimal(response.data["total_pipeline_value"]), Decimal("186500.00"))
        self.assertEqual(response.data["active_deals"], 28)
        self.assertEqual(response.data["closed_won"], 9)
        self.assertEqual(response.data["closed_lost"], 5)

    def test_stages_placeholder(self):
        response = self.client.get(reverse("pipeline-stages"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 5)
        stages = [item["stage"] for item in response.data]
        self.assertEqual(stages, ["Discovery", "Proposal", "Negotiation", "Won", "Lost"])

    def test_recent_deals_placeholder(self):
        response = self.client.get(reverse("pipeline-recent-deals"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["customer"], "Sarah Khan")

    def test_performance_placeholder(self):
        response = self.client.get(reverse("pipeline-performance"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["months"]), 12)
        self.assertEqual(response.data["months"][0], "Jan")
        self.assertEqual(response.data["deals_created"][0], 8)


class PipelineRealDataTests(APITestCase):
    """When Deal objects exist, endpoints should aggregate real data instead of placeholders."""

    def setUp(self):
        self.user = User.objects.create_user(username="tester2", password="testpass123")
        self.client.force_authenticate(user=self.user)

        self.customer = Customer.objects.create(
            first_name="Sarah", last_name="Khan", company="Global Solutions"
        )

        # Two active deals, one won, one lost -> total 4 deals
        Deal.objects.create(
            customer=self.customer,
            value=Decimal("1000.00"),
            status="discovery",
            expected_close_date=date(2026, 6, 1),
        )
        Deal.objects.create(
            customer=self.customer,
            value=Decimal("2000.00"),
            status="proposal",
            expected_close_date=date(2026, 7, 1),
        )
        Deal.objects.create(
            customer=self.customer,
            value=Decimal("3000.00"),
            status="won",
            closed_date=date(2026, 6, 15),
        )
        Deal.objects.create(
            customer=self.customer,
            value=Decimal("500.00"),
            status="lost",
        )

    def test_summary_uses_real_data(self):
        response = self.client.get(reverse("pipeline-summary"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_deals"], 4)
        self.assertEqual(Decimal(response.data["total_pipeline_value"]), Decimal("6500.00"))
        self.assertEqual(response.data["active_deals"], 2)  # discovery + proposal
        self.assertEqual(response.data["closed_won"], 1)
        self.assertEqual(response.data["closed_lost"], 1)

    def test_stages_uses_real_data(self):
        response = self.client.get(reverse("pipeline-stages"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        total_count = sum(item["deal_count"] for item in response.data)
        self.assertEqual(total_count, 4)
        # Each stage here has exactly 1 deal -> 25% each
        for item in response.data:
            self.assertEqual(item["deal_count"], 1)
            self.assertEqual(item["percentage"], 25)

    def test_recent_deals_uses_real_data(self):
        response = self.client.get(reverse("pipeline-recent-deals"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 4)
        # Most recently created deal should be first
        self.assertEqual(response.data[0]["customer"], "Sarah Khan")
        self.assertEqual(response.data[0]["company"], "Global Solutions")

    def test_performance_uses_real_data(self):
        response = self.client.get(reverse("pipeline-performance"), {"year": 2026})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # One deal was won and closed in June 2026 (index 5)
        self.assertEqual(response.data["deals_closed"][5], 1)
        self.assertEqual(response.data["revenue_generated"][5], 3000.0)