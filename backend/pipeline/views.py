from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum, Count
from django.utils import timezone
from calendar import month_name

from dashboard.models import Deal
from .serializers import (
    PipelineSummarySerializer,
    StageDistributionSerializer,
    RecentDealSerializer,
    PipelinePerformanceSerializer,
)


ACTIVE_STATUSES = ["discovery", "proposal", "negotiation"]


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pipeline_summary(request):
    """
    Return pipeline summary metrics: total deals, total pipeline value,
    active deals, closed won, closed lost. Falls back to placeholder
    data if no deals exist.
    """
    total_deals = Deal.objects.count()
    total_pipeline_value = Deal.objects.aggregate(total=Sum("value"))["total"] or 0
    active_deals = Deal.objects.filter(status__in=ACTIVE_STATUSES).count()
    closed_won = Deal.objects.filter(status="won").count()
    closed_lost = Deal.objects.filter(status="lost").count()

    if not total_deals:
        data = {
            "total_deals": 42,
            "total_pipeline_value": 186500,
            "active_deals": 28,
            "closed_won": 9,
            "closed_lost": 5,
        }
    else:
        data = {
            "total_deals": total_deals,
            "total_pipeline_value": total_pipeline_value,
            "active_deals": active_deals,
            "closed_won": closed_won,
            "closed_lost": closed_lost,
        }

    serializer = PipelineSummarySerializer(data)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stage_distribution(request):
    """
    Return deal distribution across pipeline stages (deal count,
    total value, percentage). Falls back to placeholder data if
    no deals exist.
    """
    queryset = (
        Deal.objects.values("status")
        .annotate(deal_count=Count("id"), total_value=Sum("value"))
        .order_by("status")
    )
    total_deals = sum(item["deal_count"] for item in queryset)

    if not total_deals:
        data = [
            {"stage": "Discovery", "deal_count": 12, "total_value": 45000, "percentage": 29},
            {"stage": "Proposal", "deal_count": 10, "total_value": 38000, "percentage": 24},
            {"stage": "Negotiation", "deal_count": 6, "total_value": 32000, "percentage": 14},
            {"stage": "Won", "deal_count": 9, "total_value": 51500, "percentage": 21},
            {"stage": "Lost", "deal_count": 5, "total_value": 20000, "percentage": 12},
        ]
    else:
        status_labels = dict(Deal.STATUS_CHOICES)
        data = [
            {
                "stage": status_labels.get(item["status"], item["status"]),
                "deal_count": item["deal_count"],
                "total_value": item["total_value"] or 0,
                "percentage": round((item["deal_count"] / total_deals) * 100),
            }
            for item in queryset
        ]

    serializer = StageDistributionSerializer(data, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recent_deals(request):
    """
    Return the most recently created deals with customer, company,
    value, stage, and expected closing date. Falls back to
    placeholder data if no deals exist.
    """
    queryset = Deal.objects.select_related("customer").order_by("-created_at")[:10]

    if not queryset:
        data = [
            {
                "customer": "Sarah Khan",
                "company": "Global Solutions",
                "deal_value": 8450,
                "stage": "Proposal",
                "expected_closing_date": timezone.now().date(),
            },
            {
                "customer": "Ali Raza",
                "company": "Innovatech Ltd",
                "deal_value": 6200,
                "stage": "Negotiation",
                "expected_closing_date": timezone.now().date(),
            },
        ]
    else:
        status_labels = dict(Deal.STATUS_CHOICES)
        data = [
            {
                "customer": (
                    f"{deal.customer.first_name} {deal.customer.last_name}".strip()
                    if deal.customer else "Unknown"
                ),
                "company": deal.customer.company if deal.customer and deal.customer.company else "N/A",
                "deal_value": deal.value,
                "stage": status_labels.get(deal.status, deal.status),
                "expected_closing_date": deal.expected_close_date,
            }
            for deal in queryset
        ]

    serializer = RecentDealSerializer(data, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pipeline_performance(request):
    """
    Return monthly pipeline performance: deals created, deals closed,
    and revenue generated. Falls back to placeholder data if no
    deals exist for the year.
    """
    year = int(request.query_params.get("year", timezone.now().year))
    months = [m[:3] for m in list(month_name)[1:]]

    deals_created = []
    deals_closed = []
    revenue_generated = []

    for month in range(1, 13):
        created_count = Deal.objects.filter(
            created_at__year=year, created_at__month=month
        ).count()
        closed_qs = Deal.objects.filter(
            status="won", closed_date__year=year, closed_date__month=month
        )
        closed_count = closed_qs.count()
        revenue = closed_qs.aggregate(total=Sum("value"))["total"] or 0

        deals_created.append(created_count)
        deals_closed.append(closed_count)
        revenue_generated.append(float(revenue))

    if all(v == 0 for v in deals_created) and all(v == 0 for v in deals_closed):
        deals_created = [8, 10, 9, 12, 11, 14, 13, 16, 15, 18, 17, 20]
        deals_closed = [4, 6, 5, 7, 6, 9, 8, 10, 9, 11, 10, 13]
        revenue_generated = [15000, 19000, 17000, 23000, 21000, 27000,
                              25000, 31000, 29000, 34000, 32000, 38000]

    data = {
        "months": months,
        "deals_created": deals_created,
        "deals_closed": deals_closed,
        "revenue_generated": revenue_generated,
    }

    serializer = PipelinePerformanceSerializer(data)
    return Response(serializer.data, status=status.HTTP_200_OK)