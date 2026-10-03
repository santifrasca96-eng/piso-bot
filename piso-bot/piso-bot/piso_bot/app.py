from __future__ import annotations

import html
import logging
import os
import sys
import time
from datetime import date

from .config import data_dir, load_config, load_env, profile_is_placeholder
from .fetch import BlockedError, Fetcher, FetchError
from .filters import evaluate
from .messages import draft
from .parsers import extract_listings
from .store import Store
from .telegram import Telegram

log = logging.getLogger("piso_bot")


# ------------------------------------------------------------------ búsqueda
def run_search(s: dict, cfg: dict, fetcher: Fetcher, store: Store, tg: Telegram | None, dry: bool = False) -> int:
    """Descarga una búsqueda, filtra y avisa de lo nuevo. Devuelve nº de avisos enviados."""
    try:
        page = fetcher.get(s["url"])
    except (BlockedError, FetchError) as exc:
        log.warning("%s: %s", s["name"], exc)
        _health(store, tg, s, str(exc))
        return 0

    listings = extract_listings(page, s["url"], s["source"])
    if not listings:
        log.warning("%s: 0 anuncios extraídos (¿cambió el HTML?)", s["name"])
        _health(store, tg, s, "0 anuncios extraídos: el HTML del portal puede haber cambiado")
        return 0

    first_run = not store.has_search(s["name"])
    new = [l for l in listings if not store.seen(l.uid)]
    accepted = []
    for l in new:
        ok, reasons = evaluate(l, s, cfg)
        if ok:
            accepted.append(l)
        elif not dry:
            store.add(l, s["name"], "filtered")
        else:
            log.info("  ✗ %s %s€ → %s", l.ext_id, l.price, "; ".join(reasons))

    accepted.sort(key=lambda x: x.score, reverse=True)
    limit = cfg.get("first_run_max_alerts", 10) if first_run else len(accepted)
    sent = 0
    for i, l in enumerate(accepted):
        if dry:
            log.info("  ✓ %s %s€ score=%s %s", l.ext_id, l.price, l.score, l.notes)
            continue
        if i < limit and tg:
            row = store.add(l, s["name"], "sent")
            tg.send_listing(l, row)
            sent += 1
        else:
            store.add(l, s["name"], "seen_silent")
    log.info("%s: %d extraídos, %d nuevos, %d aceptados, %d avisos", s["name"], len(listings), len(new), len(accepted), sent)
    return sent


def _health(store: Store, tg: Telegram | None, s: dict, msg: str) -> None:
    """Avisa por Telegram de un fallo de una búsqueda, como mucho una vez al día."""
    key = f"health:{s['name']}:{date.today().isoformat()}"
    if tg and not store.kv_get(key):
        store.kv_set(key, "1")
        try:
            tg.send_text(f"⚠️ <b>{html.escape(s['name'])}</b>\n{html.escape(msg)}")
        except Exception as exc:
            log.warning("no se pudo avisar del fallo: %s", exc)


def cycle(cfg: dict, fetcher: Fetcher, store: Store, tg: Telegram | None, only: str | None = None, dry: bool = False) -> int:
    total = 0
    for s in cfg["searches"]:
        if not s.get("enabled", True):
            continue
        if only and only.lower() not in s["name"].lower():
            continue
        total += run_search(s, cfg, fetcher, store, tg, dry=dry)
    return total


# ------------------------------------------------------------------ Telegram
def handle_update(u: dict, cfg: dict, store: Store, tg: Telegram) -> None:
    cb = u.get("callback_query")
    msg = u.get("message")
    chat = (cb["message"]["chat"]["id"] if cb else msg["chat"]["id"] if msg else None)
    if str(chat) != tg.chat_id:  # solo hace caso a tu chat
        return

    if msg and msg.get("text", "").startswith(("/start", "/estado")):
        c = store.counts()
        tg.send_text(
            "✅ Bot activo.\n"
            f"Avisados: {c.get('sent', 0)} · Preparados: {c.get('approved', 0)} · "
            f"Descartados: {c.get('discarded', 0)} · Filtrados: {c.get('filtered', 0)}"
        )
        return
    if not cb:
        return

    action, _, raw = cb["data"].partition(":")
    row_id = int(raw)
    l = store.get(row_id)
    if not l:
        tg.answer_callback(cb["id"], "Anuncio no encontrado")
        return
    if action == "d":
        store.set_status(row_id, "discarded")
        tg.answer_callback(cb["id"], "Descartado")
        tg.clear_buttons(chat, cb["message"]["message_id"])
    elif action == "c":
        store.set_status(row_id, "approved")
        tg.answer_callback(cb["id"], "Mensaje listo")
        text = draft(l, cfg)
        tg.send_text(
            f"✉️ <b>Borrador para contactar</b> (toca el texto para copiarlo y pégalo en el anuncio):\n\n"
            f"<pre>{html.escape(text)}</pre>\n{html.escape(l.url)}"
        )
        if l.kind == "flat":
            tg.send_text("ℹ️ Recuerda: para alquilar habitaciones del piso necesitas permiso escrito del propietario (art. 8 LAU).")


def drain(cfg: dict, store: Store, tg: Telegram) -> int:
    """Atiende los botones pulsados desde la última pasada (sin esperar). Devuelve cuántos."""
    handled = 0
    while True:
        offset = store.kv_get("tg_offset")
        try:
            updates = tg.get_updates(int(offset) if offset else None, timeout=0)
        except Exception as exc:
            log.warning("getUpdates: %s", exc)
            return handled
        if not updates:
            return handled
        for u in updates:
            try:
                handle_update(u, cfg, store, tg)
            except Exception:
                log.exception("error atendiendo update")
            store.kv_set("tg_offset", str(u["update_id"] + 1))
            handled += 1


def housekeeping(cfg: dict, store: Store, tg: Telegram) -> None:
    """Latido diario (si deja de llegar, el workflow se ha parado) y aviso de perfil sin configurar."""
    today = date.today().isoformat()
    if not store.kv_get(f"hb:{today}"):
        store.kv_set(f"hb:{today}", "1")
        c = store.counts()
        tg.send_text(
            f"🟢 Buscador activo · avisados {c.get('sent', 0)}, preparados {c.get('approved', 0)}, "
            f"descartados {c.get('discarded', 0)}, filtrados {c.get('filtered', 0)}.",
            silent=True,
        )
    if profile_is_placeholder(cfg) and not store.kv_get(f"profile:{today}"):
        store.kv_set(f"profile:{today}", "1")
        tg.send_text("⚠️ Falta configurar tu perfil (secreto PROFILE_YAML): los borradores saldrán con datos de ejemplo.")


def listen(cfg: dict, store: Store, tg: Telegram, seconds: float) -> None:
    """Atiende botones de Telegram durante `seconds` segundos."""
    end = time.time() + seconds
    while time.time() < end:
        offset = store.kv_get("tg_offset")
        try:
            updates = tg.get_updates(int(offset) if offset else None, timeout=min(25, max(1, int(end - time.time()))))
        except Exception as exc:
            log.warning("getUpdates: %s", exc)
            time.sleep(5)
            continue
        for u in updates:
            try:
                handle_update(u, cfg, store, tg)
            except Exception:
                log.exception("error atendiendo update")
            store.kv_set("tg_offset", str(u["update_id"] + 1))


# ------------------------------------------------------------------ comandos
def _build() -> tuple[dict, Fetcher, Store, Telegram | None]:
    load_env()
    cfg = load_config()
    fetcher = Fetcher(tuple(cfg.get("request_delay_seconds", [4, 9])))
    store = Store(data_dir() / "piso_bot.sqlite")
    token, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    tg = Telegram(token, chat) if token and chat and "pon_aqui" not in token else None
    return cfg, fetcher, store, tg


def cmd_run() -> None:
    cfg, fetcher, store, tg = _build()
    if not tg:
        sys.exit("Falta TELEGRAM_TOKEN / TELEGRAM_CHAT_ID en .env (mira README.md)")
    tg.send_text("🟢 Buscador arrancado. Te aviso de los anuncios nuevos.")
    while True:
        started = time.time()
        try:
            cycle(cfg, fetcher, store, tg)
        except Exception:
            log.exception("fallo en el ciclo")
        listen(cfg, store, tg, max(30, cfg.get("poll_minutes", 10) * 60 - (time.time() - started)))


def cmd_tick() -> None:
    """Una pasada completa, pensada para GitHub Actions (que la lanza cada ~10 min)."""
    cfg, fetcher, store, tg = _build()
    if not tg:
        sys.exit("Faltan los secretos TELEGRAM_TOKEN / TELEGRAM_CHAT_ID")
    drain(cfg, store, tg)          # botones pulsados desde la pasada anterior
    cycle(cfg, fetcher, store, tg)
    drain(cfg, store, tg)          # botones pulsados mientras se buscaba
    housekeeping(cfg, store, tg)


def cmd_once(args: list[str]) -> None:
    cfg, fetcher, store, tg = _build()
    dry = "--dry" in args
    only = next((a for a in args if not a.startswith("--")), None)
    cycle(cfg, fetcher, store, None if dry else tg, only=only, dry=dry)


def cmd_check_urls() -> None:
    cfg, fetcher, _, _ = _build()
    for s in cfg["searches"]:
        try:
            n = len(extract_listings(fetcher.get(s["url"]), s["url"], s["source"]))
            print(f"{'OK ' if n else 'VACÍO'}  {n:3d} anuncios  {s['name']}")
        except (BlockedError, FetchError) as exc:
            print(f"FALLO       {s['name']}: {exc}")


def cmd_chat_id() -> None:
    load_env()
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        sys.exit("Pon TELEGRAM_TOKEN en .env primero.")
    tg = Telegram(token, None)
    print("Escribe cualquier mensaje a tu bot en Telegram y espera...")
    for _ in range(12):
        for u in tg.get_updates(None, timeout=5):
            m = u.get("message")
            if m:
                print(f"TELEGRAM_CHAT_ID={m['chat']['id']}")
                return
    print("No llegó ningún mensaje. Escríbele al bot y vuelve a ejecutar.")


def cmd_dump(args: list[str]) -> None:
    """Guarda el HTML de una URL para ajustar los parsers."""
    _, fetcher, _, _ = _build()
    out = data_dir() / "dump.html"
    out.write_text(fetcher.get(args[0]), encoding="utf-8")
    print(f"Guardado en {out}")


class _RedactingFormatter(logging.Formatter):
    """Oculta el token de Telegram en los logs (en un repositorio público los logs son públicos)."""

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        secret = os.environ.get("TELEGRAM_TOKEN")
        if secret and len(secret) > 8:
            text = text.replace(secret, "***")
        return text


def main() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(_RedactingFormatter("%(asctime)s %(levelname)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    load_env()
    args = sys.argv[1:]
    cmd = args[0] if args else "run"
    if cmd == "tick":
        cmd_tick()
    elif cmd == "run":
        cmd_run()
    elif cmd == "once":
        cmd_once(args[1:])
    elif cmd == "check-urls":
        cmd_check_urls()
    elif cmd == "chat-id":
        cmd_chat_id()
    elif cmd == "dump" and len(args) > 1:
        cmd_dump(args[1:])
    else:
        print("Uso: python -m piso_bot [tick | run | once [--dry] [texto_búsqueda] | check-urls | chat-id | dump URL]")
