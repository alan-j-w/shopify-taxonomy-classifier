from django.db import models
from products.models import Product
from taxonomy.models import Category, CategoryAttribute


class Batch(models.Model):

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("PROCESSING", "Processing"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
    ]

    name = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    total_products = models.IntegerField(
        default=0
    )

    completed_products = models.IntegerField(
        default=0
    )

    failed_products = models.IntegerField(
        default=0
    )

    pending_products = models.IntegerField(
        default=0
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
        db_index=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.name or f"Batch #{self.id}"


class ClassificationResult(models.Model):

    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE
    )

    predicted_category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True
    )

    confidence_score = models.FloatField(
        default=0,
        db_index=True
    )

    review_required = models.BooleanField(
        default=False,
        db_index=True
    )

    classified_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.product.title}"


class ProductAttribute(models.Model):

    classification = models.ForeignKey(
        ClassificationResult,
        on_delete=models.CASCADE
    )

    attribute = models.ForeignKey(
        CategoryAttribute,
        on_delete=models.CASCADE
    )

    value = models.CharField(
        max_length=500
    )

    def __str__(self):
        return f"{self.attribute.name}: {self.value}"


class AlternativeCategory(models.Model):

    classification = models.ForeignKey(
        ClassificationResult,
        on_delete=models.CASCADE
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE
    )

    score = models.FloatField()

    def __str__(self):
        return self.category.name