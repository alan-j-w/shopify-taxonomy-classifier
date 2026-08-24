from django.db.models import Avg
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from products.models import Product
from classification.models import ClassificationResult, Batch
from .serializers import (
    ProductSerializer,
    ClassificationSerializer,
    BatchSerializer,
    StatsResponseSerializer,
    StatusResponseSerializer,
)


class ProductListAPIView(generics.ListAPIView):
    queryset = Product.objects.prefetch_related("images").order_by("id")
    serializer_class = ProductSerializer


class ProductDetailAPIView(generics.RetrieveAPIView):
    queryset = Product.objects.prefetch_related("images").order_by("id")
    serializer_class = ProductSerializer


class ClassificationAPIView(generics.ListAPIView):
    queryset = (
        ClassificationResult.objects
        .select_related("product", "predicted_category")
        .prefetch_related("alternativecategory_set")
        .order_by("-classified_at")
    )
    serializer_class = ClassificationSerializer


class BatchAPIView(generics.ListAPIView):
    queryset = Batch.objects.all().order_by("-created_at")
    serializer_class = BatchSerializer


class StatsAPIView(APIView):
    """
    Performance and classification metrics API.
    """
    @extend_schema(responses={200: StatsResponseSerializer})
    def get(self, request):
        total = Product.objects.count()
        completed = Product.objects.filter(status__in=["COMPLETED", "APPROVED"]).count()
        failed = Product.objects.filter(status="FAILED").count()
        review = Product.objects.filter(status="REVIEW").count()
        pending = Product.objects.filter(status__in=["PENDING", "RETRYING", "PROCESSING"]).count()

        avg_conf = ClassificationResult.objects.aggregate(avg=Avg("confidence_score"))["avg"]
        avg_confidence = round(avg_conf, 2) if avg_conf is not None else 0.0

        return Response({
            "total_products": total,
            "completed": completed,
            "failed": failed,
            "review": review,
            "pending": pending,
            "avg_confidence": avg_confidence,
        })


class ApproveProductAPIView(APIView):
    @extend_schema(request=None, responses={200: StatusResponseSerializer})
    def post(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        product.status = "APPROVED"
        product.save()
        return Response({"status": "approved"})


class RejectProductAPIView(APIView):
    @extend_schema(request=None, responses={200: StatusResponseSerializer})
    def post(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        product.status = "FAILED"
        product.save()
        return Response({"status": "rejected"})
