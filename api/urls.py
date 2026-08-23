from django.urls import path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)

from .views import (
    ProductListAPIView,
    ProductDetailAPIView,
    ClassificationAPIView,
    BatchAPIView,
    StatsAPIView,
    ApproveProductAPIView,
    RejectProductAPIView,
)

urlpatterns = [
    # Core REST Endpoints
    path("products/", ProductListAPIView.as_view(), name="api_product_list"),
    path("products/<int:pk>/", ProductDetailAPIView.as_view(), name="api_product_detail"),
    path("classifications/", ClassificationAPIView.as_view(), name="api_classification_list"),
    path("batches/", BatchAPIView.as_view(), name="api_batch_list"),
    path("stats/", StatsAPIView.as_view(), name="api_stats"),
    path("products/<int:product_id>/approve/", ApproveProductAPIView.as_view(), name="api_approve_product"),
    path("products/<int:product_id>/reject/", RejectProductAPIView.as_view(), name="api_reject_product"),

    # OpenAPI / Swagger Documentation (documents the required API)
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
