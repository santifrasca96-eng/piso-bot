from __future__ import annotations

import logging
import random
import time

import requests

log = logging.getLogger("piso_bot.fetch")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

BLOCK_MARKERS = ("captcha", "datadome", "access denied", "are you a human", "unusual traffic", "cf-chl")


class FetchError(Exception):
    """Error genérico de descarga."""


class BlockedError(FetchError):
    """El portal ha bloqueado la petición (403/429/captcha)."""


class Fetcher:
    def __init__(self, delay_range=(4, 9)):
        self.session = requests.Session()
        self.delay_range = delay_range
        self._last = 0.0

    def _sleep(self) -> None:
        wait = random.uniform(*self.delay_range) - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)

    def get(self, url: str, retries: int = 2) -> str:
        last_err: Exception | None = None
        for attempt in range(retries + 1):
            self._sleep()
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.6",
            }
            try:
                resp = self.session.get(url, headers=headers, timeout=25)
            except requests.RequestException as exc:
                last_err = FetchError(f"red: {exc}")
                time.sleep(2 ** attempt)
                continue
            finally:
                self._last = time.time()

            if resp.status_code in (403, 429):
                raise BlockedError(f"HTTP {resp.status_code} en {url}")
            if resp.status_code == 404:
                raise FetchError(f"HTTP 404 (URL incorrecta) en {url}")
            if resp.status_code >= 500:
                last_err = FetchError(f"HTTP {resp.status_code}")
                time.sleep(2 ** attempt)
                continue
            if resp.status_code != 200:
                raise FetchError(f"HTTP {resp.status_code} en {url}")

            head = resp.text[:4000].lower()
            if any(m in head for m in BLOCK_MARKERS) and len(resp.text) < 30000:
                raise BlockedError(f"posible captcha/antibot en {url}")
            return resp.text
        raise last_err or FetchError(f"no se pudo descargar {url}")
