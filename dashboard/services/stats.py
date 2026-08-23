from products.models import Product
from classification.models import Batch, ClassificationResult


def get_total_products():
    """Returns total number of products in the catalog."""
    return Product.objects.count()


def get_completed_products():
    """Returns number of successfully classified products (including manually approved)."""
    return Product.objects.filter(status__in=["COMPLETED", "APPROVED"]).count()


def get_failed_products():
    """Returns number of failed products."""
    return Product.objects.filter(status="FAILED").count()


def get_review_products():
    """Returns number of products flagged for manual review."""
    return Product.objects.filter(status="REVIEW").count()


def get_pending_products():
    """Returns number of products pending classification."""
    return Product.objects.filter(status="PENDING").count()


def get_processing_products():
    """Returns number of products currently processing."""
    return Product.objects.filter(status="PROCESSING").count()


def get_dashboard_stats():
    """Returns a consolidated dictionary of catalog and classification stats."""
    total = get_total_products()
    completed = get_completed_products()
    failed = get_failed_products()
    review = get_review_products()
    pending = get_pending_products()
    processing = get_processing_products()

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
