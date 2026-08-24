import csv
import io
import os
import pandas as pd
from django.contrib import messages
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST

from dashboard.services.stats import get_dashboard_stats
from products.models import Product, ProductImage
from classification.models import (
    ClassificationResult,
    ProductAttribute,
    AlternativeCategory,
    Batch
)
from classification.tasks import process_batch


def _clean_str(val):
    if val is None or pd.isna(val):
        return ""
    return str(val).strip()


def upload_products(request):
    """
    Handle CSV & XLSX Upload, create products with bulk_create, and spawn batch classification.
    """
    if request.method == "POST":
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            messages.error(request, "Please select a file to upload.")
            return redirect("upload_products")

        file_name = uploaded_file.name.lower()
        if not (file_name.endswith(".csv") or file_name.endswith(".xlsx") or file_name.endswith(".xls")):
            messages.error(request, "Unsupported file format. Please upload a .csv, .xlsx, or .xls file.")
            return redirect("upload_products")

        try:
            rows_data = []

            if file_name.endswith(".csv"):
                # Handle various text encodings gracefully
                raw_bytes = uploaded_file.read()
                decoded_text = None
                for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
                    try:
                        decoded_text = raw_bytes.decode(enc)
                        break
                    except (UnicodeDecodeError, LookupError):
                        continue

                if not decoded_text:
                    decoded_text = raw_bytes.decode("utf-8", errors="replace")

                reader = csv.reader(io.StringIO(decoded_text))
                header = next(reader, None)
                if header:
                    header_map = {str(h).strip().lower(): idx for idx, h in enumerate(header)}
                    
                    def get_col(row, *col_names):
                        for name in col_names:
                            idx = header_map.get(name.lower())
                            if idx is not None and idx < len(row):
                                val = row[idx].strip()
                                if val:
                                    return val
                        return ""

                    for row in reader:
                        if not any(cell.strip() for cell in row):
                            continue
                        title = get_col(row, "title", "product name", "name", "product_name") or (row[0].strip() if len(row) > 0 else "")
                        if not title:
                            continue
                        description = get_col(row, "description", "product description", "product_description") or (row[1].strip() if len(row) > 1 else "")
                        product_number = get_col(row, "product number", "product_number", "sku", "id", "model number", "model_number") or (row[2].strip() if len(row) > 2 else "")
                        category = get_col(row, "product category", "product_category", "category")
                        materials = get_col(row, "materials", "material")
                        image_1 = get_col(row, "image 1", "image_1", "image_url", "image")

                        rows_data.append({
                            "title": title,
                            "description": description,
                            "product_number": product_number,
                            "product_category": category,
                            "materials": materials,
                            "image_1": image_1,
                        })
            else:
                # Handle Excel spreadsheet
                df = pd.read_excel(uploaded_file)
                df.columns = [str(c).strip().lower() for c in df.columns]

                def get_df_val(row, *col_names):
                    for name in col_names:
                        if name.lower() in df.columns:
                            val = _clean_str(row.get(name.lower()))
                            if val:
                                return val
                    return ""

                for _, row in df.iterrows():
                    title = get_df_val(row, "title", "product name", "name", "product_name")
                    if not title:
                        continue
                    description = get_df_val(row, "description", "product description", "product_description")
                    product_number = get_df_val(row, "product number", "product_number", "sku", "model number")
                    category = get_df_val(row, "product category", "product_category", "category")
                    materials = get_df_val(row, "materials", "material")
                    image_1 = get_df_val(row, "image 1", "image_1", "image_url", "image")

                    rows_data.append({
                        "title": title,
                        "description": description,
                        "product_number": product_number,
                        "product_category": category,
                        "materials": materials,
                        "image_1": image_1,
                    })

            if not rows_data:
                messages.warning(request, "The uploaded file contained no valid product rows.")
                return redirect("upload_products")

            products_to_create = [
                Product(
                    title=item["title"][:500],
                    description=item["description"],
                    product_number=item["product_number"][:100] if item["product_number"] else None,
                    product_category=item["product_category"][:255] if item["product_category"] else None,
                    materials=item["materials"][:500] if item["materials"] else None,
                    image_1=item["image_1"] if item["image_1"] else None,
                    status="PENDING",
                )
                for item in rows_data
            ]

            import logging
            logger = logging.getLogger("classification")

            with transaction.atomic():
                Product.objects.bulk_create(products_to_create, batch_size=500)
                # Retrieve the newly created product IDs
                created_ids = list(
                    Product.objects.filter(status="PENDING")
                    .order_by("-id")[:len(products_to_create)]
                    .values_list("id", flat=True)
                )[::-1]

                batch = Batch.objects.create(
                    name=f"Upload: {uploaded_file.name}"[:255],
                    total_products=len(created_ids),
                    pending_products=len(created_ids),
                    status="PROCESSING",
                )

            logger.info(f"[Batch Creation] Created Batch #{batch.id} '{batch.name}' with {len(created_ids)} products.")

            # Dispatch Celery background task with graceful thread fallback
            try:
                process_batch.delay(batch.id, product_ids=created_ids)
                logger.info(f"[Task Dispatch] Dispatched Celery task for Batch #{batch.id}")
            except Exception as celery_err:
                logger.warning(f"[Task Fallback] Celery queue unavailable ({celery_err}), launching async processing thread for Batch #{batch.id}...")
                import threading
                threading.Thread(target=process_batch, args=(batch.id, created_ids), daemon=True).start()

            messages.success(request, f"Successfully imported {len(products_to_create)} products. Batch #{batch.id} started.")
            return redirect("batch_monitoring")

        except Exception as e:
            messages.error(request, f"Error processing catalog file: {str(e)}")
            return redirect("upload_products")

    return render(request, "dashboard/upload_products.html")


def dashboard_home(request):
    """
    Main dashboard page
    """

    stats = get_dashboard_stats()

    recent_batches = Batch.objects.order_by(
        "-created_at"
    )[:5]

    recent_completions = (
        ClassificationResult.objects
        .select_related(
            "product",
            "predicted_category"
        )
        .order_by("-classified_at")[:10]
    )

    context = {
        "stats": stats,
        "total_products": stats["total_products"],
        "completed": stats["completed_products"],
        "failed": stats["failed_products"],
        "review": stats["review_products"],
        "pending": stats["pending_products"],
        "processing": stats["processing_products"],
        "completion_rate": stats["completion_rate_percentage"],
        "recent_batches": recent_batches,
        "recent_completions": recent_completions,
    }

    return render(
        request,
        "dashboard/home.html",
        context
    )


def review_queue(request):
    """
    Products requiring manual review
    """

    search_query = request.GET.get(
        "q",
        ""
    )

    products = Product.objects.filter(
        status="REVIEW"
    )

    if search_query:
        products = products.filter(
            title__icontains=search_query
        )

    products = products.order_by("-id")

    paginator = Paginator(
        products,
        50
    )

    page_number = request.GET.get(
        "page"
    )

    page_obj = paginator.get_page(
        page_number
    )

    context = {
        "page_obj": page_obj,
        "search_query": search_query,
    }

    return render(
        request,
        "dashboard/review_queue.html",
        context
    )


def classification_results(request):
    """
    View all classification results
    """

    search_query = request.GET.get(
        "q",
        ""
    )

    results = (
        ClassificationResult.objects
        .select_related(
            "product",
            "predicted_category"
        )
        .order_by("-classified_at")
    )

    if search_query:

        results = results.filter(
            product__title__icontains=search_query
        )

    paginator = Paginator(
        results,
        100
    )

    page_number = request.GET.get(
        "page"
    )

    page_obj = paginator.get_page(
        page_number
    )

    context = {
        "page_obj": page_obj,
        "search_query": search_query,
    }

    return render(
        request,
        "dashboard/classification_results.html",
        context
    )


def batch_monitoring(request):
    """
    View to monitor all batches
    """
    batches = Batch.objects.all().order_by("-created_at")
    
    paginator = Paginator(batches, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    
    return render(
        request,
        "dashboard/batch_monitoring.html",
        {"page_obj": page_obj}
    )


def product_detail(request, product_id):
    product = get_object_or_404(Product.objects.prefetch_related("images"), id=product_id)
    result = ClassificationResult.objects.filter(product=product).select_related("predicted_category").first()
    attributes = ProductAttribute.objects.filter(classification=result).select_related("attribute") if result else []
    alternatives = AlternativeCategory.objects.filter(classification=result).select_related("category") if result else []

    return render(
        request,
        "dashboard/product_detail.html",
        {
            "product": product,
            "result": result,
            "attributes": attributes,
            "alternatives": alternatives,
        }
    )


@require_POST
def approve_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.status = "APPROVED"
    product.save(update_fields=["status"])
    return redirect("review_queue")


@require_POST
def reject_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.status = "FAILED"
    product.save(update_fields=["status"])
    return redirect("review_queue")