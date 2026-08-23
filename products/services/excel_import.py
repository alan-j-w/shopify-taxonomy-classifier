import pandas as pd
from django.db import transaction
from products.models import Product, ProductImage


def clean_val(val):
    if pd.isna(val) or val is None:
        return None
    val_str = str(val).strip()
    return val_str if val_str else None


def import_products(file_path, batch_size=500):
    df = pd.read_excel(file_path)

    # Normalize column names: strip whitespace
    df.columns = [str(col).strip() for col in df.columns]

    products_to_create = []
    product_images_data = []

    for _, row in df.iterrows():
        title = (
            clean_val(row.get("Product Name"))
            or clean_val(row.get("title"))
            or clean_val(row.get("Name"))
            or clean_val(row.get("Title"))
            or ""
        )

        if not title:
            continue

        product_number = (
            clean_val(row.get("Product Number"))
            or clean_val(row.get("product_number"))
            or clean_val(row.get("SKU"))
        )
        model_number = (
            clean_val(row.get("Model Number"))
            or clean_val(row.get("model_number"))
        )
        product_category = (
            clean_val(row.get("Product Category"))
            or clean_val(row.get("product_category"))
            or clean_val(row.get("Category"))
        )
        product_sub_category = (
            clean_val(row.get("Product Sub Category"))
            or clean_val(row.get("product_sub_category"))
            or clean_val(row.get("Sub Category"))
        )
        collection_name = (
            clean_val(row.get("Collection Name"))
            or clean_val(row.get("collection_name"))
            or clean_val(row.get("brand"))
            or clean_val(row.get("Brand"))
        )
        color_collection = (
            clean_val(row.get("Color Collection"))
            or clean_val(row.get("color_collection"))
        )
        product_color = (
            clean_val(row.get("Product Color"))
            or clean_val(row.get("product_color"))
            or clean_val(row.get("Color"))
        )
        description = (
            clean_val(row.get("Product Description"))
            or clean_val(row.get("description"))
            or clean_val(row.get("Description"))
        )
        materials = (
            clean_val(row.get("Materials"))
            or clean_val(row.get("materials"))
            or clean_val(row.get("Material"))
        )
        dimensions = (
            clean_val(row.get("Product Dimensions"))
            or clean_val(row.get("dimensions"))
            or clean_val(row.get("Dimensions"))
        )
        weight = (
            clean_val(row.get("Product Weight"))
            or clean_val(row.get("weight"))
            or clean_val(row.get("Weight"))
        )

        image_1 = clean_val(row.get("Image 1")) or clean_val(row.get("image_1")) or clean_val(row.get("image_url"))
        image_2 = clean_val(row.get("Image 2")) or clean_val(row.get("image_2"))
        image_3 = clean_val(row.get("Image 3")) or clean_val(row.get("image_3"))
        image_4 = clean_val(row.get("Image 4")) or clean_val(row.get("image_4"))

        prod = Product(
            product_number=product_number,
            model_number=model_number,
            product_category=product_category,
            product_sub_category=product_sub_category,
            collection_name=collection_name,
            color_collection=color_collection,
            product_color=product_color,
            title=title,
            description=description,
            materials=materials,
            dimensions=dimensions,
            weight=weight,
            image_1=image_1,
            image_2=image_2,
            image_3=image_3,
            image_4=image_4,
            status="PENDING",
        )
        products_to_create.append(prod)

        img_urls = []
        for i in range(1, 21):
            img_val = clean_val(row.get(f"Image {i}")) or clean_val(row.get(f"image_{i}"))
            if img_val:
                img_urls.append((i, img_val))
        product_images_data.append(img_urls)

    with transaction.atomic():
        created_products = Product.objects.bulk_create(products_to_create, batch_size=batch_size)

        images_to_bulk_create = []
        for prod_obj, img_list in zip(created_products, product_images_data):
            for order, url in img_list:
                images_to_bulk_create.append(
                    ProductImage(
                        product=prod_obj,
                        image_url=url,
                        image_order=order,
                    )
                )

        if images_to_bulk_create:
            ProductImage.objects.bulk_create(images_to_bulk_create, batch_size=batch_size)

    return len(created_products)
