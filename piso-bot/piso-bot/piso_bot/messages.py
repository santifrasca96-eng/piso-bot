from __future__ import annotations

from .models import Listing


def draft(l: Listing, cfg: dict) -> str:
    p = cfg["profile"]
    intro = (
        f"Hola, me llamo {p['name']}, tengo {p['age']} años y trabajo como {p['job']}. "
        f"Soy autónomo, con ingresos estables y documentación verificable."
    )
    if l.kind == "room":
        body = (
            f" Busco habitación a partir de {p['move_in']} con contrato de larga duración (1 año prorrogable)."
            + "".join(f" {line}" for line in p.get("extra_room_lines", []))
            + " ¿Sigue disponible?"
        )
    else:
        body = (
            f" Me interesa el piso para entrar en {p['move_in']} con contrato de larga duración"
            " (1 año prorrogable). Puedo aportar documentación y garantías adicionales."
            " Mi idea es compartirlo alquilando alguna habitación, así que quería saber si el propietario"
            " lo permitiría por escrito. ¿Sigue disponible?"
        )
    outro = f" Puedo hacer una videollamada o visitarlo en cuanto viaje a Barcelona. Mi teléfono: {p['phone']}. Gracias."
    return intro + body + outro
