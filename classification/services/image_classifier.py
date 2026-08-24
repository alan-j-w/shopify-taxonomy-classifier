import io
import json
import os
from io import BytesIO
from urllib.parse import urlparse

from google import genai
from google.genai import types
from dotenv import load_dotenv
from PIL import Image
import requests

# Load environment variables
load_dotenv()

# Initialize the new SDK client
# Note: It automatically picks up GEMINI_API_KEY from environment
try:
    client = genai.Client()
except Exception:
    client = None

# Default to active gemini-3.6-flash model
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")


def load_image(image_source):
    """
    Load an image from a local file path, URL, or file-like object.
    """
    if isinstance(image_source, Image.Image):
        return image_source

    if isinstance(image_source, str):
        parsed = urlparse(image_source)
        if parsed.scheme in ("http", "https"):
            response = requests.get(image_source, timeout=10)
            response.raise_for_status()
            return Image.open(BytesIO(response.content))
        elif os.path.exists(image_source):
            return Image.open(image_source)
        else:
            raise FileNotFoundError(f"Image not found at path: {image_source}")

    elif hasattr(image_source, "read"):
        return Image.open(image_source)

    raise ValueError(f"Unsupported image source: {type(image_source)}")


def analyze_product_image(image_path):
    """
    Receive image (path or URL), analyze image with Gemini, and return attributes dictionary.
    """
    try:
        if not client:
            raise RuntimeError("Gemini SDK not initialized (Missing API Key?)")
            
        img = load_image(image_path)

        prompt = (
            "Analyze this product image and identify its visual attributes for e-commerce catalog classification.\n"
            "Return a valid JSON object with the following keys:\n"
            "- predicted_category: Specific high-level category path (e.g., 'Sporting Goods > Athletics > Running Shoes', 'Jewelry & Watches > Watches', 'Apparel & Accessories > Clothing > Shirts & Tops')\n"
            "- product_type: Exact product type (e.g., 'Running Shoes', 'Chronograph Watch', 'Crewneck T-Shirt')\n"
            "- color: Primary and secondary colors detected (e.g., 'Red and White', 'Silver and Black', 'Navy Blue')\n"
            "- materials: Apparent materials (e.g., 'Mesh, Synthetic Foam, Rubber', 'Stainless Steel, Sapphire Crystal', '100% Cotton')\n"
            "- style: Design style or vibe (e.g., 'Athletic, Modern', 'Luxury, Classic', 'Casual, Minimalist')\n"
            "- key_features: Array of specific key features (e.g., ['Lace-up closure', 'Cushioned midsole', 'Breathable mesh upper'])\n\n"
            "IMPORTANT: Return ONLY a valid JSON object. Do not include markdown code block formatting (no ```json or ```)."
        )

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[prompt, img],
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json"
            )
        )
        response_text = response.text.strip()
        if response_text.startswith("```"):
            lines = response_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            response_text = "\n".join(lines).strip()

        return json.loads(response_text)

    except Exception as e:
        return {
            "error": str(e),
            "predicted_category": None,
            "product_type": None,
            "color": None,
            "materials": None,
            "style": None,
            "key_features": []
        }

