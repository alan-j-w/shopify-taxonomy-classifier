import logging
import traceback
from celery import shared_task
from products.models import Product
from classification.models import Batch
from classification.tasks.process_product import process_product

logger = logging.getLogger("classification")


def execute_batch_processing(batch_id, product_ids=None, async_products=False):
    """
    Core batch processing logic.
    Processes products for a given Batch, updating progress and counters in real time.
    """
    try:
        batch = Batch.objects.get(id=batch_id)
    except Batch.DoesNotExist:
        logger.error(f"[Batch Ingestion] Batch #{batch_id} does not exist.")
        return None

    logger.info(f"[Task Receipt] Processing Batch #{batch_id} (target products: {len(product_ids) if product_ids else 'ALL PENDING'})")

    try:
        if product_ids:
            pending_ids = list(
                Product.objects.filter(id__in=product_ids, status__in=["PENDING", "FAILED", "RETRYING"])
                .order_by("id")
                .values_list("id", flat=True)
            )
        else:
            pending_ids = list(
                Product.objects.filter(status__in=["PENDING", "FAILED", "RETRYING"])
                .order_by("id")
                .values_list("id", flat=True)
            )

        snapshot_count = len(pending_ids)

        batch.total_products = snapshot_count
        batch.status = "PROCESSING"
        batch.pending_products = snapshot_count
        batch.completed_products = 0
        batch.failed_products = 0
        batch.save(update_fields=["status", "total_products", "pending_products", "completed_products", "failed_products"])

        logger.info(f"[Batch Start] Batch #{batch_id} started processing {snapshot_count} products.")

        if snapshot_count == 0:
            batch.status = "COMPLETED"
            batch.save(update_fields=["status"])
            return {"batch_id": batch.id, "status": "COMPLETED"}

        if async_products:
            for product_id in pending_ids:
                process_product.delay(product_id)
            logger.info(f"Dispatched {snapshot_count} products to Celery workers.")
            return {"batch_id": batch.id, "dispatched": snapshot_count}

        # Sequential processing with per-item error isolation
        for product_id in pending_ids:
            try:
                res = process_product(product_id, rate_limit_delay=0.2)
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

        # Final status determination
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

    except Exception as top_err:
        logger.error(f"[Batch Crash] Unhandled exception in Batch #{batch_id}: {top_err}\n{traceback.format_exc()}")
        try:
            batch.status = "FAILED"
            batch.save(update_fields=["status"])
        except Exception:
            pass
        return {"batch_id": batch_id, "status": "FAILED", "error": str(top_err)}


@shared_task(bind=True)
def process_batch(self, batch_id, product_ids=None, async_products=False):
    """
    Celery task wrapper around execute_batch_processing.
    """
    return execute_batch_processing(batch_id, product_ids=product_ids, async_products=async_products)
