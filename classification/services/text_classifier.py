import json
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(
    api_key=os.getenv("GEMINI_API_KEY")
)

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
model = genai.GenerativeModel(MODEL_NAME)


def analyze_product_text(title, description=None, materials=None, category_hint=None, sub_category_hint=None):
    """
    Analyze product text metadata with Gemini and return structured taxonomy & attributes.
    """
    context_lines = [f"Product Title: {title}"]
    if description:
        context_lines.append(f"Description: {description}")
    if materials:
        context_lines.append(f"Materials: {materials}")
    if category_hint:
        context_lines.append(f"Catalog Category: {category_hint}")
    if sub_category_hint:
        context_lines.append(f"Catalog Sub Category: {sub_category_hint}")

    product_info = "\n".join(context_lines)

    prompt = (
        "Analyze the following product text information and classify it into standard Shopify e-commerce taxonomy.\n"
        f"{product_info}\n\n"
        "Return a valid JSON object with the following keys:\n"
        "- predicted_category: Standard Shopify taxonomy category path (e.g., 'Furniture > Living Room Furniture > Sofas & Couches')\n"
        "- product_type: Specific product type (e.g., 'Sofa', 'Dining Chair')\n"
        "- color: Extracted color(s)\n"
        "- materials: Extracted material(s)\n"
        "- style: Extracted design style\n"
        "- key_attributes: Object with key-value pairs of extracted attributes (e.g. {'Seat Height': '18 in', 'Assembly Required': 'No'})\n\n"
        "IMPORTANT: Return ONLY a valid JSON object. Do not include markdown code blocks (no ```json or ```)."
    )

    try:
        response = model.generate_content(prompt)
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
            "predicted_category": category_hint or "General Merchandise",
            "product_type": sub_category_hint or "General Product",
            "color": None,
            "materials": materials,
            "style": None,
            "key_attributes": {}
        }
