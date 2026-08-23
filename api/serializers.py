from rest_framework import serializers
from products.models import Product
from classification.models import ClassificationResult, Batch, AlternativeCategory


class AlternativeCategorySerializer(serializers.ModelSerializer):
    category = serializers.StringRelatedField()

    class Meta:
        model = AlternativeCategory
        fields = ["category", "score"]


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = "__all__"


class ClassificationSerializer(serializers.ModelSerializer):
    alternative_categories = AlternativeCategorySerializer(
        source="alternativecategory_set",
        many=True,
        read_only=True,
    )

    class Meta:
        model = ClassificationResult
        fields = "__all__"


class BatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Batch
        fields = "__all__"


class StatsResponseSerializer(serializers.Serializer):
    total_products = serializers.IntegerField()
    completed = serializers.IntegerField()
    failed = serializers.IntegerField()
    review = serializers.IntegerField()
    pending = serializers.IntegerField()
    avg_confidence = serializers.FloatField()


class StatusResponseSerializer(serializers.Serializer):
    status = serializers.CharField()