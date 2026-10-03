import logging

from piso_bot import app
from piso_bot.app import _RedactingFormatter, drain, housekeeping
from piso_bot.config import load_config, profile_is_placeholder
from piso_bot.store import Store

CFG = load_config()


class FakeTG:
    chat_id = "42"

    def __init__(self, batches):
        self.batches, self.texts, self.silent = list(batches), [], []

    def get_updates(self, offset, timeout=25):
        assert timeout == 0                       # en GitHub Actions no se espera
        return self.batches.pop(0) if self.batches else []

    def send_text(self, text, silent=False, **kw):
        self.texts.append(text)
        self.silent.append(silent)

    def answer_callback(self, *a, **k): ...
    def clear_buttons(self, *a): ...


def test_drain_handles_buttons_and_saves_offset(tmp_path):
    store = Store(tmp_path / "t.sqlite")
    upd = {"update_id": 10, "message": {"text": "/estado", "chat": {"id": 42}}}
    tg = FakeTG([[upd], []])
    assert drain(CFG, store, tg) == 1
    assert store.kv_get("tg_offset") == "11"
    assert any("Bot activo" in t for t in tg.texts)


def test_heartbeat_once_per_day_and_silent(tmp_path):
    store, tg = Store(tmp_path / "t.sqlite"), FakeTG([])
    housekeeping(CFG, store, tg)
    housekeeping(CFG, store, tg)
    assert sum("Buscador activo" in t for t in tg.texts) == 1
    assert tg.silent[0] is True


def test_placeholder_profile_warns(tmp_path):
    cfg = {**CFG, "profile": {**CFG["profile"], "name": "TU NOMBRE"}}
    assert profile_is_placeholder(cfg)
    store, tg = Store(tmp_path / "t.sqlite"), FakeTG([])
    housekeeping(cfg, store, tg)
    assert any("PROFILE_YAML" in t for t in tg.texts)
    assert not profile_is_placeholder(CFG)


def test_token_is_redacted_in_logs(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "123456:SECRET-TOKEN-VALUE")
    fmt = _RedactingFormatter("%(message)s")
    try:
        raise RuntimeError("fallo en https://api.telegram.org/bot123456:SECRET-TOKEN-VALUE/getUpdates")
    except RuntimeError:
        import sys
        rec = logging.LogRecord("x", logging.ERROR, __file__, 1, "error %s", ("123456:SECRET-TOKEN-VALUE",), sys.exc_info())
    out = fmt.format(rec)
    assert "SECRET-TOKEN-VALUE" not in out and "***" in out


def test_tick_command_exists():
    assert callable(app.cmd_tick)
