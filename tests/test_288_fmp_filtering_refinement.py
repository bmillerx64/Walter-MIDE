from mide.news import MATERIAL_CATALYST_SCORE, classify_headline


def test_receives_investment_is_material_positive_catalyst():
    score, flags = classify_headline(
        "Autozi Internet Technology receives $30M investment from multiple investors"
    )
    assert score >= MATERIAL_CATALYST_SCORE
    assert "capital_injection" in flags


def test_secures_funding_is_material_positive_catalyst():
    score, flags = classify_headline(
        "Company secures $12 million funding from strategic investor"
    )
    assert score >= MATERIAL_CATALYST_SCORE
    assert "capital_injection" in flags


def test_generic_investment_commentary_is_not_promoted():
    score, flags = classify_headline(
        "Analysts discuss investment opportunities across small-cap technology stocks"
    )
    assert abs(score) < MATERIAL_CATALYST_SCORE
    assert "capital_injection" not in flags


def test_offering_language_remains_negative_and_is_never_upgraded():
    score, flags = classify_headline(
        "Company receives investment through registered direct offering"
    )
    assert score < 0
    assert "registered direct" in flags
    assert "capital_injection" not in flags
