from __future__ import annotations

import re
import unicodedata

from .models import Listing


def norm(text: str) -> str:
    """Minúsculas y sin tildes, para comparar palabras clave."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.lower())


def _has(text: str, words: list[str]) -> bool:
    return any(w in text for w in words)


def evaluate(l: Listing, search: dict, cfg: dict) -> tuple[bool, list[str]]:
    """Devuelve (aceptado, motivos_de_rechazo). Rellena l.score y l.notes."""
    b, kw = cfg["budget"], cfg["keywords"]
    l.kind = search["kind"]
    text = norm(f"{l.title} {l.text}")
    reasons: list[str] = []
    notes: list[str] = []
    score = 50

    # ---- zona (solo en búsquedas amplias) ----
    zones = [norm(z) for z in search.get("zones") or []]
    if zones and not _has(text, zones):
        reasons.append("zona fuera de la lista")

    # ---- palabras que descartan ----
    hit = next((w for w in kw["reject"] if w in text), None)
    if hit:
        reasons.append(f"contiene '{hit}'")
    for rx in kw.get("reject_regex", []):
        m = re.search(rx, text)
        if m:
            reasons.append(f"contrato corto ('{m.group(0)}')")
            break

    # ---- precio ----
    if l.price is None:
        reasons.append("sin precio legible")
    elif l.kind == "room":
        if l.price > b["room_max"]:
            reasons.append(f"{l.price} € > {b['room_max']} €")
        elif l.price < b["room_min"]:
            reasons.append(f"precio sospechosamente bajo ({l.price} €)")
    else:
        if l.price > b["flat_max"]:
            reasons.append(f"{l.price} € > {b['flat_max']} €")

    # ---- tipo de anuncio ----
    looks_like_room = bool(re.search(r"\b(se alquila|alquilo|alquiler de)?\s*habitacion(es)? en (piso|alquiler|barrio|un piso)", text))
    if l.kind == "flat":
        if looks_like_room:
            reasons.append("es una habitación suelta, no un piso")
        if l.rooms is None:
            notes.append("nº de habitaciones sin confirmar")
            score -= 5
        elif l.rooms < b["flat_min_rooms"]:
            reasons.append(f"solo {l.rooms} hab.")
    else:
        m = re.search(r"de (\d+) habitaciones", text)
        if m and int(m.group(1)) > b["max_flatmates"] + 1:
            reasons.append(f"piso de {m.group(1)} habitaciones (> {b['max_flatmates']} compañeros)")

    # ---- amueblado ----
    if _has(text, kw["unfurnished"]):
        if l.kind == "flat":
            reasons.append("sin amueblar")
    elif _has(text, kw["furnished"]):
        score += 10
        notes.append("amueblado")
    elif l.kind == "flat":
        notes.append("amueblado sin confirmar")
        score -= 10

    # ---- extras que suman o restan ----
    if _has(text, kw["long_term"]):
        score += 10
        notes.append("larga duración")
    if l.kind == "flat" and _has(text, kw["sublet_ok"]):
        score += 10
        notes.append("admite subarriendo/compartir")
    if _has(text, kw["friendly"]):
        score += 8
        notes.append("acepta autónomos/sin nómina")
    if _has(text, kw["video_visit"]):
        score += 6
        notes.append("visita por videollamada")
    if _has(text, kw["agency"]):
        score -= 5
        notes.append("agencia (posibles honorarios)")
    elif "particular" in text:
        score += 8
        notes.append("particular")
    if l.kind == "room" and _has(text, kw["costs_not_included"]):
        notes.append("⚠️ gastos no incluidos: el precio real puede pasar del máximo")
        score -= 10
    if _has(text, kw["scam"]):
        notes.append("🚨 posible estafa (pide dinero/envío de llaves)")
        score -= 30

    l.score = max(0, min(100, score))
    l.notes = notes
    return (not reasons), reasons
