import json
from django.core.management.base import BaseCommand

from taxonomy.models import Category


class Command(BaseCommand):

    help = "Import Shopify Taxonomy"

    def handle(self, *args, **kwargs):

        with open(
            "data/shopify_taxonomy.json",
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        Category.objects.all().delete()

        category_map = {}

        verticals = data.get("verticals", [])

        # First Pass
        for vertical in verticals:

            for category_data in vertical.get(
                "categories",
                []
            ):

                category = Category.objects.create(
                    name=category_data["name"],
                    full_path=category_data["full_name"]
                )

                category_map[
                    category_data["id"]
                ] = category

        # Second Pass
        for vertical in verticals:

            for category_data in vertical.get(
                "categories",
                []
            ):

                parent_id = category_data.get(
                    "parent_id"
                )

                if parent_id:

                    category = category_map[
                        category_data["id"]
                    ]

                    category.parent = category_map.get(
                        parent_id
                    )

                    category.save()

        self.stdout.write(
            self.style.SUCCESS(
                "Taxonomy Imported Successfully"
            )
        )