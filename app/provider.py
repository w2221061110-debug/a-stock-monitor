from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import akshare as ak
import pandas as pd

from .models import Snapshot


SHANGHAI = ZoneInfo("Asia/Shanghai")


def _num(value, default: float | None = None) -> float | None:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _row_by_code(df: pd.DataFrame, symbol: str) -> pd.Series:
    if "代码" not in df.columns:
        raise RuntimeError("行情数据缺少“代码”字段")
    rows = df[df["代码"].astype(str).str.zfill(6) == symbol.zfill(6)]
    if rows.empty:
        raise LookupError(f"未找到 {symbol} 的行情")
    return rows.iloc[0]


class AkshareProvider:
    """AKShare/东方财富行情提供器。

    一次监控检查只拉取一份 ETF 表、一份 A 股表和一份上证指数表，
    避免针对每个代码重复请求全市场数据。
    """

    def load_spot_tables(self) -> dict[str, pd.DataFrame]:
        return {
            "etf": ak.fund_etf_spot_em(),
            "stock": ak.stock_zh_a_spot_em(),
            "index": ak.stock_zh_index_spot_em(symbol="上证系列指数"),
        }

    def snapshot_from_tables(
        self,
        symbol: str,
        asset_type: str,
        tables: dict[str, pd.DataFrame],
    ) -> Snapshot:
        asset_type = asset_type.lower()
        if asset_type == "etf":
            row = _row_by_code(tables["etf"], symbol)
            return Snapshot(
                symbol=symbol,
                name=str(row.get("名称", symbol)),
                asset_type="etf",
                price=_num(row.get("最新价"), 0.0) or 0.0,
                change_pct=_num(row.get("涨跌幅"), 0.0) or 0.0,
                open=_num(row.get("开盘价")),
                high=_num(row.get("最高价")),
                low=_num(row.get("最低价")),
                prev_close=_num(row.get("昨收")),
                volume=_num(row.get("成交量")),
                amount=_num(row.get("成交额")),
                volume_ratio=_num(row.get("量比")),
                updated_at=str(row.get("更新时间", "")) or None,
            )

        if asset_type == "stock":
            row = _row_by_code(tables["stock"], symbol)
            return Snapshot(
                symbol=symbol,
                name=str(row.get("名称", symbol)),
                asset_type="stock",
                price=_num(row.get("最新价"), 0.0) or 0.0,
                change_pct=_num(row.get("涨跌幅"), 0.0) or 0.0,
                open=_num(row.get("今开")),
                high=_num(row.get("最高")),
                low=_num(row.get("最低")),
                prev_close=_num(row.get("昨收")),
                volume=_num(row.get("成交量")),
                amount=_num(row.get("成交额")),
                volume_ratio=_num(row.get("量比")),
                updated_at=datetime.now(SHANGHAI).isoformat(timespec="seconds"),
            )

        if asset_type == "index":
            row = _row_by_code(tables["index"], symbol)
            return Snapshot(
                symbol=symbol,
                name=str(row.get("名称", symbol)),
                asset_type="index",
                price=_num(row.get("最新价"), 0.0) or 0.0,
                change_pct=_num(row.get("涨跌幅"), 0.0) or 0.0,
                open=_num(row.get("今开")),
                high=_num(row.get("最高")),
                low=_num(row.get("最低")),
                prev_close=_num(row.get("昨收")),
                volume=_num(row.get("成交量")),
                amount=_num(row.get("成交额")),
                volume_ratio=_num(row.get("量比")),
                updated_at=datetime.now(SHANGHAI).isoformat(timespec="seconds"),
            )

        raise ValueError(f"未知 asset_type: {asset_type}")

    def minute_bars(self, symbol: str, asset_type: str) -> pd.DataFrame:
        now = datetime.now(SHANGHAI)
        start = now.replace(hour=9, minute=30, second=0, microsecond=0)
        start_s = start.strftime("%Y-%m-%d %H:%M:%S")
        end_s = now.strftime("%Y-%m-%d %H:%M:%S")

        if asset_type == "etf":
            return ak.fund_etf_hist_min_em(
                symbol=symbol,
                start_date=start_s,
                end_date=end_s,
                period="1",
                adjust="",
            )
        if asset_type == "stock":
            return ak.stock_zh_a_hist_min_em(
                symbol=symbol,
                start_date=start_s,
                end_date=end_s,
                period="1",
                adjust="",
            )
        if asset_type == "index":
            return ak.index_zh_a_hist_min_em(
                symbol=symbol,
                period="1",
                start_date=start_s,
                end_date=end_s,
            )
        raise ValueError(f"未知 asset_type: {asset_type}")
