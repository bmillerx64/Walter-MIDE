from mide.gs326_near_miss_watch import near_miss_markup, near_miss_rows


def _diagnostics(rows):
    return {"post_universe_pipeline": {"pre_expansion_candidates": rows}}


def test_near_miss_watch_uses_only_existing_expansion_rejections():
    diagnostics = _diagnostics([
        {"Rank before Expansion": 1, "Symbol": "FNGR", "Expansion result": "REJECTED",
         "Participation score": 91, "Expansion score": 45,
         "Rejected because": "expansion_score = 45; required = 65"},
        {"Rank before Expansion": 2, "Symbol": "BTAI", "Expansion result": "PASSED",
         "Participation score": 80, "Expansion score": 65},
        {"Rank before Expansion": 3, "Symbol": "NCGL", "Expansion result": "REJECTED",
         "Participation score": 74, "Expansion score": 45,
         "Rejected because": "expansion_score = 45; required = 65"},
    ])

    rows = near_miss_rows(diagnostics, ranked_symbols=["BTAI"])

    assert [row["Symbol"] for row in rows] == ["FNGR", "NCGL"]
    assert all(row["Expansion result"] == "REJECTED" for row in rows)


def test_near_miss_watch_never_duplicates_ranked_candidates():
    diagnostics = _diagnostics([
        {"Rank before Expansion": 1, "Symbol": "DUO", "Expansion result": "REJECTED"},
        {"Rank before Expansion": 2, "Symbol": "FEMY", "Expansion result": "REJECTED"},
    ])

    rows = near_miss_rows(diagnostics, ranked_symbols=["DUO"], limit=3)

    assert [row["Symbol"] for row in rows] == ["FEMY"]


def test_near_miss_markup_is_explicitly_not_an_entry_signal():
    markup = near_miss_markup([
        {"Symbol": "FNGR", "Participation score": 91, "Expansion score": 45,
         "Rejected because": "expansion_score = 45; required = 65"}
    ])

    assert "NEAR-MISS WATCH" in markup
    assert "NOT ENTRY QUALIFIED" in markup
    assert "Watch only; the gate remains closed." in markup
    assert "FNGR" in markup


def test_near_miss_watch_does_not_invent_rows_without_completed_diagnostics():
    assert near_miss_rows(None) == []
    assert near_miss_rows({}) == []
