from django import forms


class ProductUploadForm(forms.Form):
    file = forms.FileField()
