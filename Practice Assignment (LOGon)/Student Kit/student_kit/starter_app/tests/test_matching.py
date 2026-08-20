from app.matching import match_order
from app.schemas import ExtractedItem, ExtractedOrder


def make_order(raw_text):
    return ExtractedOrder(
        raw_text=raw_text,
        delivery_note=None,
        items=[ExtractedItem(raw_text=raw_text, quantity=2, unit_hint=None)],
    )


def test_matches_customer_template_product():
    matched = match_order(make_order("Sonnenblumenoel Big Chef"), "CUST-DEMO")

    item = matched.items[0]
    assert item.selected.code == "OEG25"
    assert item.selected.stage == "customer_template"
    assert item.selected.score >= 85


def test_falls_back_to_catalog_for_product_outside_template():
    matched = match_order(make_order("Kartoffelsalat 2kg"), "CUST-DEMO")

    item = matched.items[0]
    assert item.selected.code == "KART02"
    assert item.selected.stage == "fallback_catalog"


def test_handles_common_multilingual_synonym():
    matched = match_order(make_order("sunflower oil big chef"), "CUST-DEMO")

    assert matched.items[0].selected.code == "OEG25"


def test_returns_alternatives():
    matched = match_order(make_order("sauce"), "CUST-DEMO", threshold=95)

    assert matched.items[0].alternatives
