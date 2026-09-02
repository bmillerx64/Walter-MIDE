from mide import ui
from mide.gs365_chime_semantic_classifier import semantic_chime_count


def test_negative_entry_ready_language_is_routine_not_three_chimes():
    assert semantic_chime_count(
        "WAIT promoted to Strengthening. Reason: participation improving. "
        "Not yet Entry Ready: VWAP confirmation is still missing."
    ) == 1


def test_developing_no_entry_review_language_is_routine():
    assert semantic_chime_count(
        "MGN. Developing. No entry review until price reclaims VWAP."
    ) == 1


def test_look_now_remains_two_even_if_phrase_says_not_yet_entry_ready():
    assert semantic_chime_count(
        "VIOT. Look Now. Not yet Entry Ready: wait for participation confirmation."
    ) == 2


def test_affirmative_entry_states_remain_three_chimes():
    assert semantic_chime_count("VIOT. Watch for Entry.") == 3
    assert semantic_chime_count("VIOT promoted to Entry Ready.") == 3
    assert semantic_chime_count("VIOT. Entry Window.") == 3
    assert semantic_chime_count("VIOT. Get Ready.") == 3


def test_closed_entry_window_is_not_high_tier():
    assert semantic_chime_count("VIOT. Entry Window closed. Continue monitoring.") == 1


def test_gs365_is_final_audio_layer():
    assert getattr(ui.play_alert, "_gs365_chime_semantics", False)
