"""Router tests. Downloads a small embedding model on first run."""
import pytest
import router
from config import ROUTER_CONFIDENCE_THRESHOLD


@pytest.mark.parametrize("query,expected", [
    ("What is your return policy?", "faq"),
    ("Can I cancel or modify my order?", "faq"),
    ("How quickly can I get my order delivered?", "faq"),
    ("Show me Samsung mobiles under 20000", "sql"),
    ("Pink Puma shoes in price range 1000 to 5000", "sql"),
    ("Find Nike shoes with the biggest discount", "sql"),
    ("Best rated headphones", "sql"),
    ("hello there", "small-talk"),
    ("what can you do?", "small-talk"),
])
def test_routes_known_intents(query, expected):
    r = router.route(query)
    assert r.name == expected
    assert r.confidence >= ROUTER_CONFIDENCE_THRESHOLD
    assert 0.0 <= r.confidence <= 1.0


def test_gibberish_has_low_confidence():
    r = router.route("asdfghjkl qwerty")
    assert r.confidence < 0.35  # would trigger a clarifying question


# --- resolve_intent: ambiguous follow-ups stick to the active search ----------
TH = ROUTER_CONFIDENCE_THRESHOLD


def test_confident_route_is_used_as_is():
    routed = router.Routed(name="faq", confidence=0.9)
    assert router.resolve_intent(routed, TH, last_intent="sql") == "faq"


def test_low_confidence_followup_sticks_to_active_search():
    # "color black" scores below threshold but should keep refining the search.
    routed = router.Routed(name="small-talk", confidence=0.24)
    assert router.resolve_intent(routed, TH, last_intent="sql") == "sql"


def test_low_confidence_with_no_active_search_is_ambiguous():
    routed = router.Routed(name="small-talk", confidence=0.24)
    assert router.resolve_intent(routed, TH, last_intent=None) is None
