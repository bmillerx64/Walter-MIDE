from mide.news import classify_headline, index_news, trusted_catalyst_source


def article(headline, created_at, source="PR Newswire"):
    return {
        "headline": headline,
        "created_at": created_at,
        "symbols": ["PLAG"],
        "source": source,
        "provider": "Financial Modeling Prep",
        "url": "https://example.test/news",
    }


def test_neutral_followup_does_not_hide_fresh_material_catalyst():
    indexed = index_news([
        article(
            "Planet Green announces strategic agreement with major customer",
            "2026-08-11T13:30:00Z",
        ),
        article(
            "Planet Green shares company update",
            "2026-08-11T13:45:00Z",
            source="TipRanks",
        ),
    ])

    assert indexed["PLAG"]["headline"].startswith("Planet Green announces strategic agreement")
    assert indexed["PLAG"]["catalyst_score"] >= 7
    assert indexed["PLAG"]["source"] == "PR Newswire"
    assert "source_quality:trusted" in indexed["PLAG"]["flags"]


def test_newer_material_financing_warning_supersedes_older_positive_catalyst():
    indexed = index_news([
        article(
            "Planet Green wins major contract award",
            "2026-08-11T13:30:00Z",
        ),
        article(
            "Planet Green announces registered direct offering",
            "2026-08-11T13:50:00Z",
            source="Business Wire",
        ),
    ])

    assert indexed["PLAG"]["headline"].endswith("registered direct offering")
    assert indexed["PLAG"]["catalyst_score"] < 0
    assert "source_quality:trusted" in indexed["PLAG"]["flags"]


def test_material_company_event_vocabulary_covers_common_momentum_catalysts():
    for headline in (
        "Company announces contract award",
        "Company signs strategic agreement",
        "Company receives regulatory clearance",
        "Company selected for government program",
        "Company reaches clinical milestone",
    ):
        score, flags = classify_headline(headline)
        assert score >= 7, (headline, score, flags)


def test_trusted_source_list_covers_wire_and_quality_examples_without_accepting_random_blog():
    for source in (
        "PR Newswire",
        "Business Wire",
        "GlobeNewswire",
        "ACCESSWIRE",
        "Reuters",
        "Benzinga",
        "TipRanks",
        "Company Press Release",
    ):
        assert trusted_catalyst_source(source) is True
    assert trusted_catalyst_source("Random Momentum Blog") is False
