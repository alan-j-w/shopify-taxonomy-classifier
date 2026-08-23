from difflib import SequenceMatcher


def calculate_confidence(text_result, image_result, matched_category):
    """
    Calculate confidence score (0.0 to 1.0) based on multimodal alignment:
    - Text prediction confidence
    - Image prediction alignment with text
    - Taxonomy database match strength
    """
    score = 0.5  # Base score

    # 1. Evaluate Text Result Quality
    if text_result and not text_result.get("error"):
        if text_result.get("predicted_category"):
            score += 0.25

    # 2. Evaluate Image Result Alignment
    if image_result and not image_result.get("error"):
        text_cat = (text_result.get("predicted_category") or "").lower()
        img_cat = (image_result.get("predicted_category") or "").lower()

        if text_cat and img_cat:
            # Check overlap / similarity between text & image predictions
            ratio = SequenceMatcher(None, text_cat, img_cat).ratio()
            if ratio > 0.4 or any(word in img_cat for word in text_cat.split() if len(word) > 3):
                score += 0.20
            else:
                score += 0.10
        elif img_cat:
            score += 0.15

    # 3. Evaluate Matched Category in Taxonomy
    if matched_category:
        score += 0.10

    # Clamp score to [0.1, 0.99]
    final_score = min(0.99, max(0.10, round(score, 2)))

    # Flag for manual review if confidence is lower than threshold
    review_required = final_score < 0.75

    return final_score, review_required
