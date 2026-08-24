# dashboard/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard_home, name="dashboard_home"),
    path("review/", views.review_queue, name="review_queue"),
    path("results/", views.classification_results, name="classification_results"),
    path("batches/", views.batch_monitoring, name="batch_monitoring"),
    path("upload/", views.upload_products, name="upload_products"),
    path("product/<int:product_id>/", views.product_detail, name="product_detail"),
    path("approve/<int:product_id>/", views.approve_product, name="approve_product"),
    path("reject/<int:product_id>/", views.reject_product, name="reject_product"),
    path("batches/<int:batch_id>/delete/", views.delete_batch, name="delete_batch"),
]
