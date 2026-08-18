from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class Snapshot:
    symbol: str
    name: str
    asset_type: str
    price: float
    change_pct: float
    open: float | None = None
    high: float | None = None
    low: float | None = None
    prev_close: float | None = None
    volume: float | None = None
    amount: float | None = None
    volume_ratio: float | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Alert:
    code: str
    symbol: str
    name: str
    severity: str
    message: str
    value: float | None = None
    threshold: float | None = None
    observed_at: str = ""

    def __post_init__(self) -> None:
        if not self.observed_at:
            self.observed_at = datetime.now().astimezone().isoformat(timespec="seconds")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
