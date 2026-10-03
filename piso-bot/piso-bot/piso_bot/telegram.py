from __future__ import annotations

import html
import logging

import requests

from .models import Listing

log = logging.getLogger("piso_bot.telegram")


class Telegram:
    def __init__(self, token: str, chat_id: str | int | None):
        self.base = f"https://api.telegram.org/bot{token}"
        self.chat_id = str(chat_id) if chat_id else None

    def _call(self, method: str, timeout: int = 30, **params):
        resp = requests.post(f"{self.base}/{method}", json=params, timeout=timeout)
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram {method}: {data.get('description')}")
        return data["result"]

    # ---- envío ----
    def send_text(self, text: str, reply_markup: dict | None = None, parse_mode: str = "HTML", silent: bool = False):
        return self._call(
            "sendMessage", chat_id=self.chat_id, text=text[:4000], parse_mode=parse_mode,
            reply_markup=reply_markup, disable_web_page_preview=True, disable_notification=silent,
        )

    def send_listing(self, l: Listing, row_id: int) -> None:
        kind = "🛏 Habitación" if l.kind == "room" else "🏠 Piso"
        lines = [
            f"<b>{kind} · {l.price} €</b> · puntuación {l.score}/100",
            (f"\U0001F4CD <b>{html.escape(l.zone)}</b>\n" if l.zone else "") + html.escape(l.title),
        ]
        facts = []
        if l.rooms:
            facts.append(f"{l.rooms} hab.")
        if l.size_m2:
            facts.append(f"{l.size_m2} m²")
        facts.append(l.source)
        lines.append(" · ".join(facts))
        if l.notes:
            lines.append("")
            lines += [f"• {html.escape(n)}" for n in l.notes]
        markup = {
            "inline_keyboard": [
                [{"text": "🔗 Abrir anuncio", "url": l.url}],
                [
                    {"text": "✅ Preparar contacto", "callback_data": f"c:{row_id}"},
                    {"text": "❌ Descartar", "callback_data": f"d:{row_id}"},
                ],
            ]
        }
        text = "\n".join(lines)
        if l.image:
            try:
                self._call("sendPhoto", chat_id=self.chat_id, photo=l.image, caption=text[:1000],
                           parse_mode="HTML", reply_markup=markup)
                return
            except Exception as exc:  # la imagen puede fallar: enviamos solo texto
                log.warning("sendPhoto falló (%s); se envía solo texto", exc)
        self.send_text(text, reply_markup=markup)

    def answer_callback(self, callback_id: str, text: str = "") -> None:
        try:
            self._call("answerCallbackQuery", callback_query_id=callback_id, text=text)
        except Exception as exc:
            log.warning("answerCallbackQuery: %s", exc)

    def clear_buttons(self, chat_id, message_id) -> None:
        try:
            self._call("editMessageReplyMarkup", chat_id=chat_id, message_id=message_id,
                       reply_markup={"inline_keyboard": []})
        except Exception as exc:
            log.debug("editMessageReplyMarkup: %s", exc)

    # ---- recepción (long polling) ----
    def get_updates(self, offset: int | None, timeout: int = 25) -> list[dict]:
        params = {"timeout": timeout, "allowed_updates": ["message", "callback_query"]}
        if offset is not None:
            params["offset"] = offset
        resp = requests.post(f"{self.base}/getUpdates", json=params, timeout=timeout + 10)
        return resp.json().get("result", [])
