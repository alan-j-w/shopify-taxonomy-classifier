from django.db import models


class Product(models.Model):

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("PROCESSING", "Processing"),
        ("RETRYING", "Retrying"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
        ("REVIEW", "Review"),
        ("APPROVED", "Approved"),
    ]

    product_number = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True
    )

    model_number = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    product_category = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    product_sub_category = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    collection_name = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    color_collection = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    product_color = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    title = models.CharField(
        max_length=500,
        db_index=True
    )

    description = models.TextField(
        blank=True,
        null=True
    )

    materials = models.TextField(
        blank=True,
        null=True
    )

    dimensions = models.TextField(
        blank=True,
        null=True
    )

    weight = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    image_1 = models.URLField(
        blank=True,
        null=True
    )

    image_2 = models.URLField(
        blank=True,
        null=True
    )

    image_3 = models.URLField(
        blank=True,
        null=True
    )

    image_4 = models.URLField(
        blank=True,
        null=True
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

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.title


class ProductImage(models.Model):

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images"
    )

    image_url = models.URLField()

    image_order = models.IntegerField(
        default=1
    )

    def __str__(self):
        return self.image_url