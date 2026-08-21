from mide.gs316_morning_mover_attention_balance import balance_attention_seeds


def _material(symbol, score=9, age=30):
    return {
        "symbol": symbol,
        "seed_type": "material_catalyst",
        "catalyst_score": score,
        "age_minutes": age,
        "attention_only": False,
    }


def _attention(symbol, age=30):
    return {
        "symbol": symbol,
        "seed_type": "morning_mover_attention",
        "catalyst_score": 0,
        "age_minutes": age,
        "attention_only": True,
    }


def test_busy_material_tape_reserves_room_for_morning_movers():
    rows = [_material(f"M{i:02d}") for i in range(25)]
    rows += [_attention(f"A{i:02d}", age=15 + i) for i in range(10)]

    selected = balance_attention_seeds(rows, limit=20)

    attention = [row for row in selected if row["seed_type"] == "morning_mover_attention"]
    material = [row for row in selected if row["seed_type"] == "material_catalyst"]
    assert len(selected) == 20
    assert len(attention) == 8
    assert len(material) == 12


def test_attention_seed_remains_zero_catalyst_credit():
    selected = balance_attention_seeds([_attention("USDE", age=45)], limit=20)

    assert selected[0]["attention_only"] is True
    assert selected[0]["catalyst_score"] == 0
    assert selected[0]["attention_priority"] == "HIGH"
    assert "morning mover" in selected[0]["attention_reason"]


def test_older_attention_is_not_marked_high_priority():
    selected = balance_attention_seeds([_attention("OLD", age=240)], limit=20)
    assert selected[0]["attention_priority"] == "NORMAL"


def test_material_catalysts_still_receive_majority_capacity():
    rows = [_material(f"M{i:02d}", score=10 - (i % 3)) for i in range(30)]
    rows += [_attention(f"A{i:02d}") for i in range(20)]

    selected = balance_attention_seeds(rows, limit=20)
    assert sum(row["seed_type"] == "material_catalyst" for row in selected) == 12
    assert sum(row["seed_type"] == "morning_mover_attention" for row in selected) == 8


def test_no_attention_does_not_reduce_material_capacity():
    rows = [_material(f"M{i:02d}") for i in range(25)]
    selected = balance_attention_seeds(rows, limit=20)
    assert len(selected) == 20
    assert all(row["seed_type"] == "material_catalyst" for row in selected)
