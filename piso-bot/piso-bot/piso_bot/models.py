from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Listing:
    source: str
    ext_id: str
    url: str
    title: str = ""
    price: int | None = None
    rooms: int | None = None
    size_m2: int | None = None
    zone: str = ""
    text: str = ""
    image: str | None = None
    kind: str = "flat"  # "flat" | "room"
    score: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def uid(self) -> str:
        return f"{self.source}:{self.ext_id}"
