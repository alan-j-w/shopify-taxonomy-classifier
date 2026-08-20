from django.db import models
from products.models import Product
from taxonomy.models import Category


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
        default=0
    )

    review_required = models.BooleanField(
        default=False
    )

    classified_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.product.title}"

from taxonomy.models import CategoryAttribute

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