"""Extracción genérica de anuncios a partir del HTML de un listado.

En vez de depender de clases CSS (que los portales cambian), se buscan los enlaces a fichas
de anuncio por el patrón de su URL y se sube por el DOM hasta la tarjeta más pequeña que
contiene un precio. Si un portal cambia su HTML, basta con ajustar `LINK_PATTERNS`.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .models import Listing

# Habitaclia: .../alquiler-...-i12345678901234.htm   ·   Milanuncios: .../titulo-123456789.htm
LINK_PATTERNS = {
    "habitaclia": r"-i(\d{6,})\.htm",
    "milanuncios": r"-(\d{6,})\.htm",
    "idealista": r"/inmueble/(\d{6,})/",
}

PRICE_RE = re.compile(r"(?<![\d,.])(\d{1,3}(?:\.\d{3})+|\d{2,5})\s*(?:€|euros?\b)(?!\s*/\s*m[²2])", re.I)
ROOMS_RE = re.compile(r"(\d{1,2})\s*(?:hab\b|habs\b|habit|dorm)", re.I)
SIZE_RE = re.compile(r"(\d{2,3})\s*m(?:²|2)", re.I)


def parse_price(text: str) -> int | None:
    for m in PRICE_RE.finditer(text):
        value = int(m.group(1).replace(".", ""))
        if value >= 100:
            return value
    return None


def parse_rooms(text: str) -> int | None:
    m = ROOMS_RE.search(text)
    return int(m.group(1)) if m else None


def parse_size(text: str) -> int | None:
    m = SIZE_RE.search(text)
    return int(m.group(1)) if m else None


def _image(card) -> str | None:
    img = card.find("img")
    if not img:
        return None
    for attr in ("src", "data-src", "data-lazy", "data-original"):
        val = img.get(attr)
        if val and val.startswith("http") and "placeholder" not in val:
            return val
    return None


def _title(card, link_re: str) -> str:
    candidates = []
    for a in card.find_all("a", href=True):
        if re.search(link_re, a["href"]):
            t = a.get("title") or a.get_text(" ", strip=True)
            if t:
                candidates.append(t.strip())
    if candidates:
        return max(candidates, key=len)[:160]
    h = card.find(["h2", "h3", "h4"])
    if h:
        return h.get_text(" ", strip=True)[:160]
    return card.get_text(" ", strip=True)[:100]


def extract_listings(html: str, base_url: str, source: str) -> list[Listing]:
    link_re = LINK_PATTERNS[source]
    soup = BeautifulSoup(html, "lxml")
    found: dict[str, Listing] = {}

    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"].split("#")[0])
        m = re.search(link_re, href)
        if not m:
            continue
        ext_id = m.group(1)
        if ext_id in found:
            continue

        card = a
        for _ in range(7):
            parent = card.parent
            if parent is None or parent.name in ("body", "html"):
                break
            card = parent
            text = card.get_text(" ", strip=True)
            if "€" in text and len(text) > 40:
                break
        text = card.get_text(" ", strip=True)
        if len(text) > 2500:  # contenedor demasiado grande: no es una tarjeta
            text = a.get_text(" ", strip=True)
            card = a

        found[ext_id] = Listing(
            source=source,
            ext_id=ext_id,
            url=href,
            title=_title(card, link_re),
            price=parse_price(text),
            rooms=parse_rooms(text),
            size_m2=parse_size(text),
            text=text[:1500],
            image=_image(card),
        )
    return list(found.values())
