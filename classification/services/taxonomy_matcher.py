import re
import logging
from difflib import SequenceMatcher
from django.core.cache import cache
from django.db.models import Q
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
    Load all categories from cache or DB to optimize 14k category lookups.
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
    Match a predicted category string against taxonomy Category database using cache.
    Returns (primary_category, alternatives_list)
    where alternatives_list is a list of tuples: (Category, score)
    """
    if not predicted_category_text:
        return None, []

    pred_clean = clean_text(predicted_category_text)
    pred_parts = [p.strip() for p in predicted_category_text.replace(">", "/").split("/") if p.strip()]
    leaf_name = pred_parts[-1] if pred_parts else predicted_category_text

    taxonomy = get_cached_taxonomy()

    # 1. Exact cached lookup
    pred_lower = predicted_category_text.strip().lower()
    leaf_lower = leaf_name.strip().lower()

    matched_id = taxonomy["by_path_lower"].get(pred_lower) or taxonomy["by_name_lower"].get(leaf_lower)
    if matched_id:
        try:
            exact_match = Category.objects.get(id=matched_id)
            alternatives = []
            similar_cats = Category.objects.filter(
                Q(name__icontains=leaf_name) | Q(full_path__icontains=leaf_name)
            ).exclude(id=exact_match.id)[:top_k]
            for cat in similar_cats:
                score = round(similarity_ratio(predicted_category_text, cat.full_path), 2)
                alternatives.append((cat, max(0.5, score)))
            return exact_match, alternatives
        except Category.DoesNotExist:
            pass

    # 2. Filter candidates by leaf name or keywords in DB
    candidates = Category.objects.filter(
        Q(name__icontains=leaf_name) | Q(full_path__icontains=leaf_name)
    )[:50]

    if not candidates.exists() and len(pred_parts) > 1:
        candidates = Category.objects.filter(
            Q(name__icontains=pred_parts[-2]) | Q(full_path__icontains=pred_parts[-2])
        )[:50]

    if not candidates.exists():
        words = [w for w in clean_text(leaf_name).split() if len(w) > 3]
        if words:
            q_obj = Q()
            for w in words:
                q_obj |= Q(name__icontains=w) | Q(full_path__icontains=w)
            candidates = Category.objects.filter(q_obj)[:50]

    if not candidates.exists():
        first_cat = Category.objects.first()
        return first_cat, []

    # Score candidates
    scored = []
    for cat in candidates:
        score = similarity_ratio(predicted_category_text, cat.full_path)
        if cat.name.lower() == leaf_name.lower():
            score = max(score, 0.9)
        scored.append((cat, round(score, 2)))

    scored.sort(key=lambda x: x[1], reverse=True)

    primary = scored[0][0] if scored else None
    alternatives = scored[1:top_k + 1] if len(scored) > 1 else []

    return primary, alternatives
