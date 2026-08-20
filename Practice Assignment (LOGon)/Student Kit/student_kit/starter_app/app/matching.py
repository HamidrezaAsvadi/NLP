from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Iterable, List

from .sample_data import CATALOG, CUSTOMER_HISTORY
from .schemas import ExtractedOrder, MatchedItem, MatchedOrder, Product, ProductCandidate


SYNONYMS = {
    "oil": "oel",
    "ol": "oel",
    "oele": "oel",
    "oleo": "oel",
    "sunflower": "sonnenblumenoel",
    "sunfloweroil": "sonnenblumenoel",
    "egg": "eier",
    "eggs": "eier",
    "large": "l",
    "puree": "puree",
    "piree": "puree",
    "pueree": "puree",
    "fruchtpueree": "fruchtpuree",
    "potato": "kartoffel",
    "salad": "salat",
}


def normalize(value: str) -> str:
    value = value.lower()
    value = (
        value.replace("ae", "a")
        .replace("oe", "o")
        .replace("ue", "u")
        .replace("ss", "ss")
    )
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def tokens(value: str) -> List[str]:
    result = []
    for token in normalize(value).split():
        result.append(SYNONYMS.get(token, token))
    return result


def product_search_text(product: Product) -> str:
    return " ".join(
        [product.code, product.description, product.unit, product.package_size, *product.aliases]
    )


def token_overlap_score(left: Iterable[str], right: Iterable[str]) -> int:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0
    overlap = len(left_set & right_set)
    return round(100 * overlap / len(left_set))


def text_similarity(left: str, right: str) -> int:
    left_norm = normalize(left)
    right_norm = normalize(right)
    if not left_norm or not right_norm:
        return 0
    sequence = round(100 * SequenceMatcher(None, left_norm, right_norm).ratio())
    overlap = token_overlap_score(tokens(left), tokens(right))
    return max(sequence, overlap)


def history_products(customer_code: str) -> List[Product]:
    history_codes = set(CUSTOMER_HISTORY.get(customer_code, []))
    return [product for product in CATALOG if product.code in history_codes]


def score_product(raw_text: str, product: Product, customer_code: str) -> ProductCandidate:
    base = text_similarity(raw_text, product_search_text(product))
    history_boost = 8 if product.code in CUSTOMER_HISTORY.get(customer_code, []) else 0
    score = min(100, base + history_boost)
    stage = "customer_template" if history_boost else "catalog"
    explanation = (
        f"Matched '{raw_text}' against {product.code}; base score {base}"
        f"{' plus customer-history boost' if history_boost else ''}."
    )
    return ProductCandidate(
        code=product.code,
        description=product.description,
        unit=product.unit,
        package_size=product.package_size,
        score=score,
        stage=stage,
        explanation=explanation,
    )


def rank_products(raw_text: str, products: List[Product], customer_code: str) -> List[ProductCandidate]:
    ranked = [score_product(raw_text, product, customer_code) for product in products]
    return sorted(ranked, key=lambda candidate: candidate.score, reverse=True)


def match_order(order: ExtractedOrder, customer_code: str, threshold: int = 85) -> MatchedOrder:
    matched_items: List[MatchedItem] = []
    template_products = history_products(customer_code)

    for item in order.items:
        template_ranked = rank_products(item.raw_text, template_products, customer_code)
        selected = template_ranked[0] if template_ranked else None
        alternatives: List[ProductCandidate] = template_ranked[1:4]

        if selected is None or selected.score < threshold:
            full_ranked = rank_products(item.raw_text, CATALOG, customer_code)
            selected = full_ranked[0]
            selected.stage = "fallback_catalog"
            alternatives = [candidate for candidate in full_ranked[1:4] if candidate.code != selected.code]

        matched_items.append(
            MatchedItem(
                raw_text=item.raw_text,
                requested_quantity=item.quantity,
                requested_unit_hint=item.unit_hint,
                selected=selected,
                alternatives=alternatives,
            )
        )

    return MatchedOrder(
        customer_code=customer_code,
        delivery_note=order.delivery_note,
        items=matched_items,
    )
