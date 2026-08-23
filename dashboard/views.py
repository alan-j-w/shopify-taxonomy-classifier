from django.shortcuts import render, redirect
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST

from dashboard.services.stats import get_dashboard_stats

from products.models import Product
from classification.models import (
    ClassificationResult,
    ProductAttribute,
    AlternativeCategory,
    Batch
)
import csv
import io
from django.contrib import messages
from classification.tasks import process_batch

def upload_products(request):
    """
    Handle CSV Upload, create products, and spawn batch classification
    """
    if request.method == "POST":
        csv_file = request.FILES.get("file")
        if not csv_file:
            messages.error(request, "Please upload a valid CSV file.")
            return redirect("upload_products")
            
        if not csv_file.name.endswith('.csv'):
            messages.error(request, "File must be a CSV format.")
            return redirect("upload_products")
            
        try:
            data_set = csv_file.read().decode('UTF-8')
            io_string = io.StringIO(data_set)
            # Read header
            reader = csv.reader(io_string, delimiter=',', quotechar='"')
            header = next(reader, None)
            
            products_to_create = []
            for row in reader:
                if len(row) >= 1 and row[0].strip():
                    title = row[0].strip()
                    description = row[1].strip() if len(row) > 1 else ""
                    product_number = row[2].strip() if len(row) > 2 else ""
                    
                    products_to_create.append(
                        Product(
                            title=title,
                            description=description,
                            product_number=product_number,
                            status="PENDING"
                        )
                    )
            
            if products_to_create:
                Product.objects.bulk_create(products_to_create)
                
                # Create a batch
                batch = Batch.objects.create(
                    total_products=len(products_to_create),
                    status="PROCESSING"
                )
                
                # Dispatch Celery Task
                process_batch.delay(batch.id)
                
                messages.success(request, f"Successfully uploaded {len(products_to_create)} products and started Batch #{batch.id}.")
                return redirect("batch_monitoring")
            else:
                messages.warning(request, "The uploaded CSV was empty or contained invalid rows.")
                return redirect("upload_products")
                
        except Exception as e:
            messages.error(request, f"Error processing file: {str(e)}")
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


def product_detail(
    request,
    product_id
):

    product = Product.objects.get(
        id=product_id
    )

    result = ClassificationResult.objects.filter(
        product=product
    ).first()

    attributes = ProductAttribute.objects.filter(
        classification=result
    )

    alternatives = AlternativeCategory.objects.filter(
        classification=result
    )

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
def approve_product(
    request,
    product_id
):

    product = Product.objects.get(
        id=product_id
    )

    product.status = "APPROVED"

    product.save()

    return redirect(
        "review_queue"
    )


@require_POST
def reject_product(
    request,
    product_id
):

    product = Product.objects.get(
        id=product_id
    )

    product.status = "FAILED"

    product.save()

    return redirect(
        "review_queue"
    )