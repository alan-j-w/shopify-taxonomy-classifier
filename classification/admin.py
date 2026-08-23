from django.contrib import admin
from .models import (
    Batch,
    ClassificationResult,
    ProductAttribute,
    AlternativeCategory
)

admin.site.register(Batch)
admin.site.register(ClassificationResult)
admin.site.register(ProductAttribute)
admin.site.register(AlternativeCategory)