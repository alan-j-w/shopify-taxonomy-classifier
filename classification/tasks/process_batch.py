import logging
import traceback
from celery import shared_task
from products.models import Product
from classification.models import Batch
from classification.tasks.process_product import process_product

logger = logging.getLogger("classification")


@shared_task(bind=True)
def process_batch(self, batch_id, async_products=False):
    """
    Process products for a given Batch.

    Takes a snapshot of all PENDING/FAILED products at the time the batch
    starts. Only those products are tracked against this batch's counters,
    preventing double-counting across concurrent or sequential batches.

    Features:
    - Error Isolation: Failure on one product does not halt the batch.
    - Progress Tracking: Updates completed/failed/pending counts per iteration.
    - Resume Capability: Processes PENDING and FAILED/RETRYING products.
    - Async delegation: Dispatches individual jobs to Celery if async_products=True.
    """
    try:
        batch = Batch.objects.get(id=batch_id)
    except Batch.DoesNotExist:
        logger.error(f"Batch #{batch_id} does not exist.")
        return None

    # Snapshot the PENDING products at this moment.
    # Use a list of IDs so the count is fixed and we only process this batch's work.
    pending_ids = list(
        Product.objects.filter(status__in=["PENDING", "FAILED", "RETRYING"])
        .order_by("id")
        .values_list("id", flat=True)
    )
    snapshot_count = len(pending_ids)

    # Set total_products from the snapshot (override any incorrect pre-set value)
    batch.total_products = snapshot_count
    batch.status = "PROCESSING"
    batch.pending_products = snapshot_count
    batch.completed_products = 0
    batch.failed_products = 0
    batch.save(update_fields=["status", "total_products", "pending_products", "completed_products", "failed_products"])

    logger.info(f"Starting batch #{batch_id} with {snapshot_count} items.")

    if async_products:
        for product_id in pending_ids:
            process_product.delay(product_id)
        logger.info(f"Dispatched {snapshot_count} products to Celery workers.")
        return {"batch_id": batch.id, "dispatched": snapshot_count}

    # Sequential processing with error isolation
    for product_id in pending_ids:
        try:
            res = process_product(product_id, rate_limit_delay=1.0)
            if res:
                batch.completed_products += 1
            else:
                batch.failed_products += 1
        except Exception as err:
            logger.error(f"[Error Isolation] Failed product #{product_id}: {err}\n{traceback.format_exc()}")
            batch.failed_products += 1

        batch.pending_products = max(
            0,
            batch.total_products - (batch.completed_products + batch.failed_products),
        )
        batch.save(update_fields=["completed_products", "failed_products", "pending_products"])

    # Final status determination: only mark COMPLETED when all items are done (pending_products == 0)
    if batch.pending_products == 0:
        if batch.total_products > 0 and batch.failed_products == batch.total_products:
            batch.status = "FAILED"
        else:
            batch.status = "COMPLETED"
    else:
        if batch.completed_products == 0 and batch.failed_products > 0:
            batch.status = "FAILED"
        else:
            batch.status = "PROCESSING"

    batch.save(update_fields=["status"])
    logger.info(f"Batch #{batch_id} finished. Completed: {batch.completed_products}, Failed: {batch.failed_products}")
    return {"batch_id": batch.id, "status": batch.status}
