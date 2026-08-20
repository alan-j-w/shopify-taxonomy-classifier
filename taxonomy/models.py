from django.db import models


class Category(models.Model):

    name = models.CharField(
        max_length=255
    )

    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='children'
    )

    full_path = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.full_path


class CategoryAttribute(models.Model):

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE
    )

    name = models.CharField(
        max_length=255
    )

    def __str__(self):
        return self.name