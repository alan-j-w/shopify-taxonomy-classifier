from django.db.models import Count, Q
from products.models import Product
from classification.models import Batch, ClassificationResult


def get_dashboard_stats():
    """Returns a consolidated dictionary of catalog and classification stats via a single DB query."""
    counts = Product.objects.aggregate(
        total=Count("id"),
        completed=Count("id", filter=Q(status__in=["COMPLETED", "APPROVED"])),
        failed=Count("id", filter=Q(status="FAILED")),
        review=Count("id", filter=Q(status="REVIEW")),
        pending=Count("id", filter=Q(status="PENDING")),
        processing=Count("id", filter=Q(status="PROCESSING")),
    )

    total = counts["total"] or 0
    completed = counts["completed"] or 0
    failed = counts["failed"] or 0
    review = counts["review"] or 0
    pending = counts["pending"] or 0
    processing = counts["processing"] or 0

    completion_rate = round((completed / total * 100), 1) if total > 0 else 0.0

    return {
        "total_products": total,
        "completed_products": completed,
        "failed_products": failed,
        "review_products": review,
        "pending_products": pending,
        "processing_products": processing,
        "completion_rate_percentage": completion_rate,
        "total_batches": Batch.objects.count(),
        "total_classifications": ClassificationResult.objects.count(),
    }
