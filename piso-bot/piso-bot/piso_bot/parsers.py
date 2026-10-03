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

# Habitaclia: formato nuevo /alquiler/<tipo>/<zona>/<ciudad>/<uuid>/d  (y el antiguo ...-i12345678901234.htm)
# Milanuncios: .../titulo-123456789.htm
UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
LINK_PATTERNS = {
    "habitaclia": rf"(?:-i(\d{{6,}})\.htm|/({UUID})/d(?:[/?#]|$))",
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


def _agencies(card) -> str:
    """Etiqueta 'agencia:<nombre>' por cada enlace /inmobiliaria/<nombre>-<n>/ de la tarjeta (Habitaclia)."""
    names = set()
    for a in card.find_all("a", href=True):
        if a["href"].startswith("/inmobiliaria/"):
            slug = a["href"].strip("/").split("/")[-1]
            names.add(re.sub(r"-\d+$", "", slug))
    return "".join(f" agencia:{n}" for n in sorted(names))


def _pretty(slug: str) -> str:
    slug = re.sub(r"-capital$", "", slug.strip().lower())
    return " ".join(w.capitalize() if w not in ("de", "del", "la", "el", "les", "i") else w
                    for w in slug.replace("_", "-").split("-") if w)


def parse_zone(href: str, title: str) -> str:
    """Ubicación legible, p. ej. 'Poblenou, Barcelona'. Primero de la URL de Habitaclia
    (.../<zona>/<ciudad>/<uuid>/d), si no del título ('... en <zona>')."""
    m = re.search(r"/alquiler/(?:[^/]+/)*?([^/]+)/([^/]+)/" + UUID + r"/d", href)
    if m:
        zone, city = _pretty(m.group(1)), _pretty(m.group(2))
        if zone.lower() in ("n a", "na", ""):
            return city
        return zone if zone.lower() == city.lower() else f"{zone}, {city}"
    t = re.search(r"\ben\s+([^,|·]{3,60}?)(?:\s*[,|·].*)?$", title.strip(), re.I)
    return t.group(1).strip() if t else ""


def _title(card, link_re: str) -> str:
    label = card.get("aria-label")
    if label:
        return label.strip()[:160]
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
        ext_id = next(g for g in m.groups() if g)
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
        article = a.find_parent("article")
        if article is not None:  # si la página usa <article>, esa es la tarjeta
            card = article
        text = card.get_text(" ", strip=True)
        if len(text) > 2500:  # contenedor demasiado grande: no es una tarjeta
            text = a.get_text(" ", strip=True)
            card = a
        text += _agencies(card)

        title = _title(card, link_re)
        found[ext_id] = Listing(
            source=source,
            ext_id=ext_id,
            url=href,
            title=title,
            zone=parse_zone(href, title),
            price=parse_price(text),
            rooms=parse_rooms(text),
            size_m2=parse_size(text),
            text=text[:1500],
            image=_image(card),
        )
    return list(found.values())
