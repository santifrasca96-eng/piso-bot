import pytest

from piso_bot.config import load_config
from piso_bot.filters import evaluate
from piso_bot.messages import draft
from piso_bot.models import Listing

CFG = load_config()
FLAT = {"name": "t", "kind": "flat"}
ROOM = {"name": "t", "kind": "room", "zones": ["sants", "nou barris"]}


def L(**kw):
    base = dict(source="habitaclia", ext_id="1", url="https://x", title="", text="", price=1000, rooms=2)
    base.update(kw)
    return Listing(**base)


def test_flat_ok_and_scores_extras():
    l = L(title="Piso en Nou Barris", text="Amueblado. Contrato larga duración. Se admite subarrendar. Particular.")
    ok, why = evaluate(l, FLAT, CFG)
    assert ok, why
    assert l.score >= 80


def test_flat_too_expensive():
    ok, why = evaluate(L(price=1500), FLAT, CFG)
    assert not ok and any("1500" in w for w in why)


def test_flat_one_room_rejected():
    ok, _ = evaluate(L(rooms=1), FLAT, CFG)
    assert not ok


def test_temporada_rejected():
    ok, why = evaluate(L(text="Alquiler de temporada, amueblado"), FLAT, CFG)
    assert not ok and any("temporada" in w for w in why)


def test_short_contract_regex_rejected():
    ok, _ = evaluate(L(text="contrato de 6 meses, amueblado"), FLAT, CFG)
    assert not ok
    ok, _ = evaluate(L(text="contrato de 12 meses, amueblado"), FLAT, CFG)
    assert ok


def test_unfurnished_flat_rejected():
    ok, _ = evaluate(L(text="Piso sin amueblar"), FLAT, CFG)
    assert not ok


def test_flat_search_rejects_single_room_ad():
    ok, _ = evaluate(L(title="Habitación en piso compartido Nou Barris"), FLAT, CFG)
    assert not ok


def test_room_budget_and_zone():
    ok, _ = evaluate(L(kind="room", price=550, rooms=None, title="Habitación en Sants"), ROOM, CFG)
    assert ok
    ok, why = evaluate(L(price=650, rooms=None, title="Habitación en Sants"), ROOM, CFG)
    assert not ok
    ok, why = evaluate(L(price=500, rooms=None, title="Habitación en Gràcia"), ROOM, CFG)
    assert not ok and any("zona" in w for w in why)


def test_room_too_many_flatmates():
    ok, _ = evaluate(L(price=500, rooms=None, title="Habitación en Sants", text="piso de 8 habitaciones"), ROOM, CFG)
    assert not ok
    ok, _ = evaluate(L(price=500, rooms=None, title="Habitación en Sants", text="piso de 4 habitaciones"), ROOM, CFG)
    assert ok


def test_scam_and_costs_flags_but_not_rejected():
    l = L(price=500, rooms=None, title="Habitación en Sants", text="estoy en el extranjero, envío las llaves. gastos no incluidos")
    ok, _ = evaluate(l, ROOM, CFG)
    assert ok and any("estafa" in n for n in l.notes) and any("gastos" in n for n in l.notes)
    assert l.score < 30


def test_accents_normalised():
    ok, _ = evaluate(L(text="Alquiler de TEMPORADA"), FLAT, CFG)
    assert not ok
    l = L(text="Acepto AUTÓNOMOS y extranjeros; AMUEBLADO")
    evaluate(l, FLAT, CFG)
    assert any("autónomos" in n for n in l.notes)


def test_no_price_rejected():
    ok, _ = evaluate(L(price=None), FLAT, CFG)
    assert not ok


@pytest.mark.parametrize("kind", ["flat", "room"])
def test_draft_mentions_key_facts(kind):
    text = draft(L(kind=kind), CFG)
    assert "Santiago" in text and "enero de 2027" in text and "autónomo" in text
    assert ("subarrendar" in text or "alquilando" in text) == (kind == "flat")
