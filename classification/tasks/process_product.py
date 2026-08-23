import hashlib
import logging
import time
import traceback
from celery import shared_task
from django.core.cache import cache
from django.db import transaction

from products.models import Product
from taxonomy.models import Category, CategoryAttribute
from classification.models import (
    ClassificationResult,
    ProductAttribute,
    AlternativeCategory,
)
from classification.services.text_classifier import analyze_product_text
from classification.services.image_classifier import analyze_product_image
from classification.services.taxonomy_matcher import match_taxonomy
from classification.services.confidence_engine import calculate_confidence

logger = logging.getLogger("classification")


def compute_product_hash(product):
    """
    Generate SHA-256 hash of product attributes to detect duplicate classification requests.
    """
    raw = f"{product.title}|{product.description}|{product.materials}|{product.product_category}|{product.image_1}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_product(self, product_id, rate_limit_delay=1.0):
    """
    Celery background task to process a single product with retry logic,
    rate limit protection, and caching.
    """
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        logger.error(f"Product #{product_id} not found in database.")
        return None

    # Skip already completed/approved products unless forced
    if product.status in ["COMPLETED", "APPROVED"]:
        logger.info(f"Product #{product_id} already has status {product.status}. Skipping.")
        return None

    product.status = "PROCESSING"
    product.save(update_fields=["status"])
    logger.info(f"Processing Product #{product_id}: '{product.title}'")

    # Rate limiting delay to protect Gemini API quotas
    if rate_limit_delay > 0:
        time.sleep(rate_limit_delay)

    try:
        # 1. Product Hash Caching Check
        p_hash = compute_product_hash(product)
        cache_key = f"classification_hash_{p_hash}"
        cached_result_id = cache.get(cache_key)

        if cached_result_id:
            try:
                existing_result = ClassificationResult.objects.get(id=cached_result_id)
                logger.info(f"Cache hit for product #{product_id} (matched result #{existing_result.id})")
                product.status = "REVIEW" if existing_result.review_required else "COMPLETED"
                product.save(update_fields=["status"])
                return existing_result.id
            except ClassificationResult.DoesNotExist:
                cache.delete(cache_key)

        # 2. Text Analysis
        text_result = analyze_product_text(
            title=product.title,
            description=product.description,
            materials=product.materials,
            category_hint=product.product_category,
            sub_category_hint=product.product_sub_category,
        )

        # 3. Image Analysis
        image_result = None
        img_source = product.image_1 or (product.images.first().image_url if product.images.exists() else None)
        if img_source:
            try:
                image_result = analyze_product_image(img_source)
            except Exception as img_err:
                logger.warning(f"Image analysis error on #{product_id} ({img_source}): {img_err}")
                image_result = {"error": str(img_err)}

        # 4. Taxonomy Matching
        category_query = (
            (text_result.get("predicted_category") if text_result else None)
            or (image_result.get("predicted_category") if image_result else None)
            or product.product_category
            or product.title
        )
        primary_cat, alternatives = match_taxonomy(category_query)

        # 5. Confidence Calculation
        confidence, review_required = calculate_confidence(
            text_result=text_result,
            image_result=image_result,
            matched_category=primary_cat,
        )

        with transaction.atomic():
            result, _ = ClassificationResult.objects.update_or_create(
                product=product,
                defaults={
                    "predicted_category": primary_cat,
                    "confidence_score": confidence,
                    "review_required": review_required,
                },
            )

            ProductAttribute.objects.filter(classification=result).delete()
            AlternativeCategory.objects.filter(classification=result).delete()

            for alt_cat, alt_score in alternatives:
                AlternativeCategory.objects.create(
                    classification=result,
                    category=alt_cat,
                    score=alt_score,
                )

            if primary_cat:
                combined_attrs = {}
                if text_result:
                    if text_result.get("color"):
                        combined_attrs["Color"] = text_result["color"]
                    if text_result.get("materials"):
                        combined_attrs["Materials"] = text_result["materials"]
                    if text_result.get("product_type"):
                        combined_attrs["Product Type"] = text_result["product_type"]
                    for k, v in text_result.get("key_attributes", {}).items():
                        combined_attrs[str(k)] = str(v)

                if image_result and not image_result.get("error"):
                    if image_result.get("color") and "Color" not in combined_attrs:
                        combined_attrs["Color"] = image_result["color"]
                    if image_result.get("materials") and "Materials" not in combined_attrs:
                        combined_attrs["Materials"] = image_result["materials"]
                    if image_result.get("style"):
                        combined_attrs["Style"] = image_result["style"]

                for attr_name, attr_val in combined_attrs.items():
                    if attr_val:
                        cat_attr, _ = CategoryAttribute.objects.get_or_create(
                            category=primary_cat,
                            name=attr_name,
                        )
                        ProductAttribute.objects.create(
                            classification=result,
                            attribute=cat_attr,
                            value=str(attr_val)[:500],
                        )

            product.status = "REVIEW" if review_required else "COMPLETED"
            product.save(update_fields=["status"])

            # Cache successful result hash for 7 days
            cache.set(cache_key, result.id, timeout=86400 * 7)

        logger.info(
            f"Successfully classified product #{product_id} -> '{primary_cat}' (Confidence: {confidence:.2f})"
        )
        return result.id

    except Exception as exc:
        logger.error(f"Error classifying product #{product_id}: {exc}\n{traceback.format_exc()}")
        
        # Check Celery retries
        current_retries = getattr(self.request, "retries", 0) if hasattr(self, "request") else 0
        if current_retries < getattr(self, "max_retries", 3) and hasattr(self, "retry"):
            product.status = "RETRYING"
            product.save(update_fields=["status"])
            logger.warning(f"Scheduling retry {current_retries + 1} for product #{product_id} in 60s...")
            raise self.retry(exc=exc, countdown=60)
        else:
            product.status = "FAILED"
            product.save(update_fields=["status"])
            return None
