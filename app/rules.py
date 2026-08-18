from __future__ import annotations

from statistics import median

import pandas as pd

from .models import Alert, Snapshot


def _series(df: pd.DataFrame, name: str) -> list[float]:
    if name not in df.columns:
        return []
    values = pd.to_numeric(df[name], errors="coerce").dropna().tolist()
    return [float(v) for v in values]


def evaluate_index_cross(
    snapshot: Snapshot,
    bars: pd.DataFrame,
    threshold: float,
) -> list[Alert]:
    closes = _series(bars, "收盘")
    if len(closes) < 2:
        return []
    prev_price, current = closes[-2], closes[-1]
    if prev_price < threshold <= current:
        return [
            Alert(
                code="index_cross_up",
                symbol=snapshot.symbol,
                name=snapshot.name,
                severity="high",
                message=f"{snapshot.name}向上突破 {threshold:.0f} 点",
                value=current,
                threshold=threshold,
            )
        ]
    if prev_price >= threshold > current:
        return [
            Alert(
                code="index_cross_down",
                symbol=snapshot.symbol,
                name=snapshot.name,
                severity="high",
                message=f"{snapshot.name}向下跌破 {threshold:.0f} 点",
                value=current,
                threshold=threshold,
            )
        ]
    return []


def evaluate_quick_move(
    snapshot: Snapshot,
    bars: pd.DataFrame,
    window_minutes: int,
    up_pct: float,
    down_pct: float,
) -> list[Alert]:
    closes = _series(bars, "收盘")
    if len(closes) < window_minutes + 1:
        return []
    base = closes[-(window_minutes + 1)]
    current = closes[-1]
    if base <= 0:
        return []
    move_pct = (current / base - 1.0) * 100.0
    if move_pct >= up_pct:
        return [
            Alert(
                code="quick_rise",
                symbol=snapshot.symbol,
                name=snapshot.name,
                severity="medium",
                message=f"{snapshot.name}近 {window_minutes} 分钟快速拉升 {move_pct:.2f}%",
                value=move_pct,
                threshold=up_pct,
            )
        ]
    if move_pct <= down_pct:
        return [
            Alert(
                code="quick_drop",
                symbol=snapshot.symbol,
                name=snapshot.name,
                severity="high",
                message=f"{snapshot.name}近 {window_minutes} 分钟快速跳水 {move_pct:.2f}%",
                value=move_pct,
                threshold=down_pct,
            )
        ]
    return []


def evaluate_volume_surge(
    snapshot: Snapshot,
    bars: pd.DataFrame,
    lookback: int,
    ratio_alert: float,
) -> list[Alert]:
    volumes = _series(bars, "成交量")
    if len(volumes) < 4:
        return []
    history = [v for v in volumes[-(lookback + 1):-1] if v > 0]
    current = volumes[-1]
    if not history or current <= 0:
        return []
    baseline = median(history)
    if baseline <= 0:
        return []
    ratio = current / baseline
    if ratio >= ratio_alert:
        return [
            Alert(
                code="volume_surge",
                symbol=snapshot.symbol,
                name=snapshot.name,
                severity="medium",
                message=f"{snapshot.name}当前 1 分钟成交量约为近段中位数的 {ratio:.2f} 倍",
                value=ratio,
                threshold=ratio_alert,
            )
        ]
    return []


def evaluate_relative_strength(
    snapshot: Snapshot,
    index_snapshot: Snapshot,
    gap_pct: float,
) -> list[Alert]:
    if snapshot.asset_type != "etf":
        return []
    gap = snapshot.change_pct - index_snapshot.change_pct
    if gap >= gap_pct:
        return [
            Alert(
                code="etf_relative_strong",
                symbol=snapshot.symbol,
                name=snapshot.name,
                severity="medium",
                message=f"{snapshot.name}相对上证指数强 {gap:.2f} 个百分点",
                value=gap,
                threshold=gap_pct,
            )
        ]
    if gap <= -gap_pct:
        return [
            Alert(
                code="etf_relative_weak",
                symbol=snapshot.symbol,
                name=snapshot.name,
                severity="medium",
                message=f"{snapshot.name}相对上证指数弱 {abs(gap):.2f} 个百分点",
                value=gap,
                threshold=-gap_pct,
            )
        ]
    return []


def evaluate_limit_open(
    snapshot: Snapshot,
    limit_pct: float | None,
    tolerance_price: float,
) -> list[Alert]:
    if snapshot.asset_type != "stock" or not limit_pct:
        return []
    if snapshot.prev_close is None or snapshot.high is None or snapshot.prev_close <= 0:
        return []

    limit_price = round(snapshot.prev_close * (1.0 + limit_pct / 100.0) + 1e-9, 2)
    touched_limit = snapshot.high >= limit_price - tolerance_price / 2
    opened = snapshot.price <= limit_price - tolerance_price
    if touched_limit and opened:
        return [
            Alert(
                code="limit_up_opened",
                symbol=snapshot.symbol,
                name=snapshot.name,
                severity="high",
                message=f"{snapshot.name}曾触及约 {limit_price:.2f} 的涨停价，当前已开板至 {snapshot.price:.2f}",
                value=snapshot.price,
                threshold=limit_price,
            )
        ]
    return []
