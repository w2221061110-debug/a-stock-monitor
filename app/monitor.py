from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import Alert, Snapshot
from .provider import AkshareProvider
from .rules import (
    evaluate_index_cross,
    evaluate_limit_open,
    evaluate_quick_move,
    evaluate_relative_strength,
    evaluate_volume_surge,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config.yaml"


class StockMonitor:
    def __init__(self, config_path: str | Path = DEFAULT_CONFIG) -> None:
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.provider = AkshareProvider()

    def _load_config(self) -> dict[str, Any]:
        with self.config_path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    @property
    def watchlist(self) -> list[dict[str, Any]]:
        return list(self.config.get("watchlist", []))

    def quote(self, symbol: str, asset_type: str) -> Snapshot:
        return self.provider.snapshot(symbol, asset_type)

    def check(self) -> dict[str, Any]:
        rules = self.config["rules"]
        index_cfg = self.config["index"]

        # 实时快照改为逐标的查询，并带东方财富 -> 腾讯备用源。
        # 这样云主机遇到东方财富全市场分页接口断连时，不会整次 502。
        index_snapshot = self.provider.snapshot(index_cfg["symbol"], "index")
        snapshots: list[Snapshot] = [index_snapshot]
        alerts: list[Alert] = []
        errors: list[dict[str, str]] = []

        try:
            index_bars = self.provider.minute_bars(index_snapshot.symbol, "index")
            alerts.extend(
                evaluate_index_cross(
                    index_snapshot,
                    index_bars,
                    float(index_cfg["threshold"]),
                )
            )
        except Exception as exc:  # 分钟行情失败只记录，不中断快照
            errors.append({"symbol": index_snapshot.symbol, "stage": "minute", "error": str(exc)})

        for item in self.watchlist:
            symbol = str(item["symbol"])
            asset_type = str(item["asset_type"])
            try:
                snapshot = self.provider.snapshot(symbol, asset_type)
                snapshots.append(snapshot)

                alerts.extend(
                    evaluate_relative_strength(
                        snapshot,
                        index_snapshot,
                        float(rules["etf_relative_strength_gap_pct"]),
                    )
                )
                alerts.extend(
                    evaluate_limit_open(
                        snapshot,
                        float(item["limit_pct"]) if item.get("limit_pct") else None,
                        float(rules["limit_open_tolerance_price"]),
                    )
                )

                try:
                    bars = self.provider.minute_bars(symbol, asset_type)
                    alerts.extend(
                        evaluate_quick_move(
                            snapshot,
                            bars,
                            int(rules["quick_move_window_minutes"]),
                            float(rules["quick_move_up_pct"]),
                            float(rules["quick_move_down_pct"]),
                        )
                    )
                    alerts.extend(
                        evaluate_volume_surge(
                            snapshot,
                            bars,
                            int(rules["volume_lookback_minutes"]),
                            float(rules["volume_ratio_alert"]),
                        )
                    )
                except Exception as exc:
                    errors.append({"symbol": symbol, "stage": "minute", "error": str(exc)})
            except Exception as exc:
                errors.append({"symbol": symbol, "stage": "spot", "error": str(exc)})

        return {
            "index": index_snapshot.to_dict(),
            "snapshots": [s.to_dict() for s in snapshots],
            "alerts": [a.to_dict() for a in alerts],
            "errors": errors,
        }
