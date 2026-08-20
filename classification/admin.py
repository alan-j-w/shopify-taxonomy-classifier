from django.contrib import admin
from .models import (
    ClassificationResult,
    ProductAttribute,
    AlternativeCategory
)

admin.site.register(ClassificationResult)
admin.site.register(ProductAttribute)
admin.site.register(AlternativeCategory)