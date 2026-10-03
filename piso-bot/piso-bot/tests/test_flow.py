from piso_bot.app import handle_update, run_search
from piso_bot.config import load_config
from piso_bot.store import Store

CFG = load_config()

HTML = """
<article><h3><a href="/alquiler-piso-x-i1111111111111.htm">Piso en Nou Barris</a></h3>
<p>1.100 € 2 hab. 60 m² amueblado larga duración</p></article>
<article><h3><a href="/alquiler-piso-y-i2222222222222.htm">Ático en Port</a></h3>
<p>2.400 € 3 hab. 120 m²</p></article>
<article><h3><a href="/alquiler-piso-z-i3333333333333.htm">Piso temporada</a></h3>
<p>900 € 2 hab. alquiler de temporada</p></article>
"""


class FakeFetcher:
    def get(self, url):
        return HTML


class FakeTG:
    chat_id = "42"

    def __init__(self):
        self.sent, self.texts, self.answers = [], [], []

    def send_listing(self, l, row_id):
        self.sent.append((l, row_id))

    def send_text(self, text, **kw):
        self.texts.append(text)

    def answer_callback(self, cid, text=""):
        self.answers.append(text)

    def clear_buttons(self, *a):
        pass


SEARCH = {"name": "Piso Nou Barris (test)", "source": "habitaclia", "kind": "flat",
          "url": "https://www.habitaclia.com/alquiler-nou_barris-barcelona.htm"}


def test_full_flow(tmp_path):
    store, tg = Store(tmp_path / "t.sqlite"), FakeTG()
    assert run_search(SEARCH, CFG, FakeFetcher(), store, tg) == 1     # solo el piso bueno
    assert run_search(SEARCH, CFG, FakeFetcher(), store, tg) == 0     # sin repetir
    listing, row = tg.sent[0]
    assert listing.ext_id == "1111111111111" and listing.price == 1100

    # botón "Preparar contacto" desde el chat correcto
    cb = {"callback_query": {"id": "x", "data": f"c:{row}", "message": {"message_id": 7, "chat": {"id": 42}}}}
    handle_update(cb, CFG, store, tg)
    assert store.counts()["approved"] == 1
    assert any("Borrador" in t for t in tg.texts) and any("art. 8" in t for t in tg.texts)

    # un chat ajeno es ignorado
    n = len(tg.texts)
    cb["callback_query"]["message"]["chat"]["id"] = 999
    handle_update(cb, CFG, store, tg)
    assert len(tg.texts) == n


def test_first_run_limit(tmp_path):
    cfg = {**CFG, "first_run_max_alerts": 0}
    store, tg = Store(tmp_path / "t.sqlite"), FakeTG()
    assert run_search(SEARCH, cfg, FakeFetcher(), store, tg) == 0
    assert store.counts().get("seen_silent") == 1
