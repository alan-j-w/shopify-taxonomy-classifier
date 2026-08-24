import logging
import traceback
from celery import shared_task
from products.models import Product
from classification.models import Batch
from classification.tasks.process_product import process_product

logger = logging.getLogger("classification")


def execute_batch_processing(batch_id, product_ids=None, async_products=False, is_resume=False):
    """
    Core batch processing logic.

    - When called fresh (is_resume=False): resets all counters to accurately
      track only the products in this run.
    - When called as a resume (is_resume=True): preserves existing completed/failed
      counters and only processes remaining PENDING/FAILED/RETRYING items.
    - Never fails the entire batch due to one product's error.
    - Handles Gemini 429 rate limit at the batch level by marking products
      FAILED and continuing; the 'Retry' button re-enqueues them.
    """
    try:
        batch = Batch.objects.get(id=batch_id)
    except Batch.DoesNotExist:
        logger.error(f"[Batch Ingestion] Batch #{batch_id} does not exist.")
        return None

    logger.info(
        f"[Task Receipt] {'Resuming' if is_resume else 'Starting'} Batch #{batch_id} "
        f"(explicit product_ids: {len(product_ids) if product_ids else 'None'})"
    )

    try:
        # Determine which products to process
        if product_ids:
            # Explicit list supplied (fresh upload)
            pending_ids = list(
                Product.objects.filter(id__in=product_ids, status__in=["PENDING", "FAILED", "RETRYING"])
                .order_by("id")
                .values_list("id", flat=True)
            )
        else:
            # Resume: pick up remaining unfinished items globally (no specific product_ids scoped)
            pending_ids = list(
                Product.objects.filter(status__in=["PENDING", "FAILED", "RETRYING"])
                .order_by("id")
                .values_list("id", flat=True)
            )

        snapshot_count = len(pending_ids)

        if is_resume:
            # Preserve existing progress; just update status and pending count
            batch.status = "PROCESSING"
            batch.pending_products = snapshot_count
            batch.save(update_fields=["status", "pending_products"])
        else:
            # Fresh start: reset all counters to reflect this batch's scope
            batch.total_products = snapshot_count
            batch.status = "PROCESSING"
            batch.pending_products = snapshot_count
            batch.completed_products = 0
            batch.failed_products = 0
            batch.save(update_fields=["status", "total_products", "pending_products", "completed_products", "failed_products"])

        logger.info(f"[Batch Start] Batch #{batch_id}: {snapshot_count} items to process.")

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
        # A small delay avoids hammering Gemini when processing many products
        INTER_PRODUCT_DELAY = 0.2

        for product_id in pending_ids:
            try:
                res = process_product(product_id, rate_limit_delay=INTER_PRODUCT_DELAY)
                if res:
                    batch.completed_products += 1
                else:
                    # process_product returned None: already done, skipped, or API fallback
                    # Count as completed (it handled its own status)
                    batch.completed_products += 1
            except Exception as err:
                err_str = str(err).lower()
                if "429" in err_str or "quota" in err_str or "rate" in err_str:
                    logger.warning(
                        f"[Rate Limit] Gemini quota hit on product #{product_id}. "
                        f"Marking as FAILED for retry. Error: {err}"
                    )
                else:
                    logger.error(
                        f"[Error Isolation] Failed product #{product_id}: {err}\n{traceback.format_exc()}"
                    )
                batch.failed_products += 1
                # Ensure product is marked as FAILED so Retry can pick it up
                try:
                    Product.objects.filter(id=product_id, status="PROCESSING").update(status="FAILED")
                except Exception:
                    pass

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
            # Some items remain (edge case): keep as PROCESSING
            batch.status = "PROCESSING"

        batch.save(update_fields=["status"])
        logger.info(
            f"Batch #{batch_id} finished. Status={batch.status}, "
            f"Completed={batch.completed_products}, Failed={batch.failed_products}, "
            f"Pending={batch.pending_products}"
        )
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
def process_batch(self, batch_id, product_ids=None, async_products=False, is_resume=False):
    """
    Celery task wrapper around execute_batch_processing.
    """
    return execute_batch_processing(
        batch_id,
        product_ids=product_ids,
        async_products=async_products,
        is_resume=is_resume,
    )
