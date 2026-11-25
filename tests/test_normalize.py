
import utils.normalize as normalize


def test_exact_hinglish_word():
    assert normalize.normalize_text("bewakoof") == "idiot"


def test_uppercase_hinglish_word():
    assert normalize.normalize_text("PAGAL") == "insane"


def test_multiple_hinglish_words():
    result = normalize.normalize_text("bewakoof pagal")
    assert result == "idiot insane"


def test_short_words_remain_unchanged():
    assert normalize.normalize_text("gal hat mar") == "gal hat mar"


def test_ordinary_english_remains_unchanged():
    text = "computer science is interesting"
    assert normalize.normalize_text(text) == text


def test_empty_string():
    assert normalize.normalize_text("") == ""


def test_unavailable_fuzzy_matching(monkeypatch):
    monkeypatch.setattr(normalize, "FUZZY_AVAILABLE", False)
    text = "bewakoof pagal"
    assert normalize.normalize_text(text) == text
