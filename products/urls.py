from django.urls import path
from .views import upload_products

urlpatterns = [
    path(
        "upload/",
        upload_products,
        name="upload_products"
    )
]
