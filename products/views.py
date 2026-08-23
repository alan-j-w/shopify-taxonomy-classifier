import os
from django.shortcuts import render
from .forms import ProductUploadForm
from .services.excel_import import import_products


def upload_products(request):
    message = None

    if request.method == "POST":
        form = ProductUploadForm(
            request.POST,
            request.FILES
        )

        if form.is_valid():
            uploaded_file = request.FILES["file"]
            file_path = f"temp_{uploaded_file.name}"

            try:
                with open(file_path, "wb+") as destination:
                    for chunk in uploaded_file.chunks():
                        destination.write(chunk)

                count = import_products(file_path)
                message = f"Successfully imported {count} products."
            finally:
                if os.path.exists(file_path):
                    os.remove(file_path)
    else:
        form = ProductUploadForm()

    return render(
        request,
        "products/upload.html",
        {
            "form": form,
            "message": message
        }
    )