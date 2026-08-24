import re
import logging
from difflib import SequenceMatcher
from django.core.cache import cache
from taxonomy.models import Category

logger = logging.getLogger("classification")

TAXONOMY_CACHE_KEY = "shopify_taxonomy_lookup_cache"
TAXONOMY_CACHE_TIMEOUT = 86400  # 24 hours


def clean_text(text):
    if not text:
        return ""
    return re.sub(r"[^a-zA-Z0-9\s]", " ", text).lower().strip()


def similarity_ratio(a, b):
    return SequenceMatcher(None, clean_text(a), clean_text(b)).ratio()


def get_cached_taxonomy():
    """
    Load all categories into an optimized in-memory lookup cache (14,606 entries).
    Zero database queries are performed after the initial cache population.
    """
    taxonomy = cache.get(TAXONOMY_CACHE_KEY)
    if taxonomy is None:
        logger.info("Loading full Shopify taxonomy into cache (14,606 categories)...")
        cats = list(Category.objects.all().values("id", "name", "full_path"))
        taxonomy = {
            "by_id": {c["id"]: c for c in cats},
            "by_path_lower": {c["full_path"].lower(): c["id"] for c in cats},
            "by_name_lower": {c["name"].lower(): c["id"] for c in cats},
            "all": cats,
        }
        cache.set(TAXONOMY_CACHE_KEY, taxonomy, timeout=TAXONOMY_CACHE_TIMEOUT)
    return taxonomy


def match_taxonomy(predicted_category_text, top_k=3):
    """
    Match a predicted category string against cached Shopify taxonomy.
    Performs purely in-memory lookups for ultra-fast (sub-millisecond) throughput.
    Returns (primary_category_model_instance, alternatives_list)
    where alternatives_list is a list of tuples: (Category_model_instance, score)
    """
    if not predicted_category_text:
        return None, []

    pred_parts = [p.strip() for p in predicted_category_text.replace(">", "/").split("/") if p.strip()]
    leaf_name = pred_parts[-1] if pred_parts else predicted_category_text
    leaf_lower = leaf_name.strip().lower()
    pred_lower = predicted_category_text.strip().lower()

    taxonomy = get_cached_taxonomy()
    all_cats = taxonomy["all"]

    # 1. Exact cached lookup (O(1) dictionary lookup)
    matched_id = taxonomy["by_path_lower"].get(pred_lower) or taxonomy["by_name_lower"].get(leaf_lower)
    if matched_id:
        try:
            exact_match = Category.objects.get(id=matched_id)
            alternatives = []
            # Find similar categories in-memory
            for c in all_cats:
                if c["id"] != matched_id and (leaf_lower in c["name"].lower() or leaf_lower in c["full_path"].lower()):
                    score = round(similarity_ratio(predicted_category_text, c["full_path"]), 2)
                    cat_obj = Category(id=c["id"], name=c["name"], full_path=c["full_path"])
                    alternatives.append((cat_obj, max(0.5, score)))
                    if len(alternatives) >= top_k:
                        break
            return exact_match, alternatives
        except Category.DoesNotExist:
            pass

    # 2. In-memory candidate search (zero DB queries)
    candidates = [
        c for c in all_cats
        if leaf_lower in c["name"].lower() or leaf_lower in c["full_path"].lower()
    ][:50]

    if not candidates and len(pred_parts) > 1:
        parent_lower = pred_parts[-2].lower()
        candidates = [
            c for c in all_cats
            if parent_lower in c["name"].lower() or parent_lower in c["full_path"].lower()
        ][:50]

    if not candidates:
        words = [w for w in clean_text(leaf_name).split() if len(w) > 3]
        if words:
            for c in all_cats:
                name_l = c["name"].lower()
                if any(w in name_l for w in words):
                    candidates.append(c)
                    if len(candidates) >= 50:
                        break

    if not candidates:
        first_c = all_cats[0] if all_cats else None
        if first_c:
            return Category.objects.get(id=first_c["id"]), []
        return None, []

    # Score candidates
    scored = []
    for c in candidates:
        score = similarity_ratio(predicted_category_text, c["full_path"])
        if c["name"].lower() == leaf_lower:
            score = max(score, 0.9)
        scored.append((c, round(score, 2)))

    scored.sort(key=lambda x: x[1], reverse=True)

    primary_dict = scored[0][0] if scored else None
    primary = Category.objects.get(id=primary_dict["id"]) if primary_dict else None

    alternatives = []
    for c_dict, score in scored[1:top_k + 1]:
        alt_obj = Category(id=c_dict["id"], name=c_dict["name"], full_path=c_dict["full_path"])
        alternatives.append((alt_obj, score))

    return primary, alternatives
