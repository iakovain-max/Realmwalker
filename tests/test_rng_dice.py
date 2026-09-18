import pytest

from realmwalker.core import dice
from realmwalker.core.rng import RNG


def test_same_seed_same_sequence():
    a, b = RNG(42), RNG(42)
    assert [a.randint(1, 100) for _ in range(20)] == [b.randint(1, 100) for _ in range(20)]


def test_children_are_independent_and_reproducible():
    root = RNG(7)
    m1 = root.child("map")
    root.random()  # drawing from the parent must not shift the child
    m2 = RNG(7).child("map")
    assert [m1.random() for _ in range(5)] == [m2.random() for _ in range(5)]
    assert RNG(7).child("a").random() != RNG(7).child("b").random()


def test_state_round_trip():
    r = RNG(3)
    r.random()
    state = r.get_state()
    expected = [r.random() for _ in range(5)]
    restored = RNG.from_state(state)
    assert [restored.random() for _ in range(5)] == expected


def test_numpy_generator_is_seeded():
    assert (RNG(5).numpy().random(4) == RNG(5).numpy().random(4)).all()


@pytest.mark.parametrize("expr,expected", [("2d6+3", (2, 6, 3)), ("d20", (1, 20, 0)), ("1d4-1", (1, 4, -1)), ("5", (0, 1, 5))])
def test_parse(expr, expected):
    assert dice.parse(expr) == expected


def test_parse_rejects_nonsense():
    with pytest.raises(dice.DiceError):
        dice.parse("two dragons")


def test_roll_ranges():
    rng = RNG(1)
    for _ in range(500):
        r = dice.roll("2d6+3", rng)
        assert 5 <= r.total <= 15
        assert len(r.rolls) == 2


def test_critical_doubles_dice():
    r = dice.roll("1d8+2", RNG(1), double_dice=True)
    assert len(r.rolls) == 2


def test_advantage_takes_higher_and_disadvantage_lower():
    rng = RNG(9)
    for _ in range(200):
        a = dice.d20(rng, advantage=True)
        assert a.natural == max(a.rolls)
        d = dice.d20(rng, disadvantage=True)
        assert d.natural == min(d.rolls)


def test_advantage_and_disadvantage_cancel():
    r = dice.d20(RNG(2), advantage=True, disadvantage=True)
    assert len(r.rolls) == 1 and not r.advantage and not r.disadvantage


def test_check_text_format():
    result = dice.CheckResult("Persuasion", dice.D20Roll(14, [14]), 3, 15)
    assert result.text() == "Persuasion: 14 + 3 = 17 vs DC 15 — success."
    fail = dice.CheckResult("Stealth", dice.D20Roll(4, [4]), -1, 12)
    assert fail.text() == "Stealth: 4 - 1 = 3 vs DC 12 — failure."


def test_ability_modifier():
    assert [dice.ability_modifier(s) for s in (1, 8, 9, 10, 11, 15, 20)] == [-5, -1, -1, 0, 0, 2, 5]
