"""Router tests. Downloads a small embedding model on first run."""
import pytest
import router


@pytest.mark.parametrize("query,expected", [
    ("What is your return policy?", "faq"),
    ("Show me nike shoes under 3000", "sql"),
    ("hello there", "small-talk"),
])
def test_routes_known_intents(query, expected):
    r = router.route(query)
    assert r.name == expected
    assert 0.0 <= r.confidence <= 1.0


def test_gibberish_has_low_confidence():
    r = router.route("asdfghjkl qwerty")
    assert r.confidence < 0.35  # would trigger a clarifying question
