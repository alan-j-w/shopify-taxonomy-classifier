from django.db import models


class Product(models.Model):

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("PROCESSING", "Processing"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
        ("REVIEW", "Review"),
    ]

    title = models.CharField(max_length=500)

    description = models.TextField(
        blank=True,
        null=True
    )

    brand = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    product_type = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    image_url = models.URLField(
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.title