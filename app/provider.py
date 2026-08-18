from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import akshare as ak
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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


def _eastmoney_secid(symbol: str, asset_type: str) -> str:
    symbol = symbol.zfill(6)
    if asset_type == "index":
        market = 0 if symbol.startswith("399") else 1
    else:
        market = 1 if symbol.startswith(("5", "6", "9")) else 0
    return f"{market}.{symbol}"


def _tencent_code(symbol: str, asset_type: str) -> str:
    symbol = symbol.zfill(6)
    if asset_type == "index":
        prefix = "sz" if symbol.startswith("399") else "sh"
    else:
        prefix = "sh" if symbol.startswith(("5", "6", "9")) else "sz"
    return f"{prefix}{symbol}"


class AkshareProvider:
    """A股行情提供器。

    云主机对东方财富的全市场分页接口偶尔会遇到 RemoteDisconnected，
    所以实时快照优先使用东方财富单标的接口，并以腾讯行情作为备用。
    AKShare 仍用于分钟线；分钟线失败会由 monitor 层降级为错误记录，
    不再让整次监控请求直接 502。
    """

    def __init__(self, timeout: float = 8.0) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        retry = Retry(
            total=2,
            connect=2,
            read=2,
            backoff_factor=0.25,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/126 Safari/537.36"
                )
            }
        )

    def snapshot(self, symbol: str, asset_type: str) -> Snapshot:
        errors: list[str] = []
        try:
            return self._eastmoney_snapshot(symbol, asset_type)
        except Exception as exc:
            errors.append(f"eastmoney={type(exc).__name__}: {exc}")

        try:
            return self._tencent_snapshot(symbol, asset_type)
        except Exception as exc:
            errors.append(f"tencent={type(exc).__name__}: {exc}")

        raise RuntimeError("实时行情源均失败；" + " | ".join(errors))

    def _eastmoney_snapshot(self, symbol: str, asset_type: str) -> Snapshot:
        url = "https://push2.eastmoney.com/api/qt/stock/get"
        params = {
            "fltt": "2",
            "invt": "2",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "secid": _eastmoney_secid(symbol, asset_type),
            "fields": "f43,f44,f45,f46,f47,f48,f50,f57,f58,f60,f170",
        }
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data")
        if not data:
            raise RuntimeError(f"东方财富未返回 {symbol} 数据")

        price = _num(data.get("f43"), 0.0) or 0.0
        prev_close = _num(data.get("f60"))
        change_pct = _num(data.get("f170"))
        if change_pct is None and prev_close not in (None, 0) and price:
            change_pct = (price / prev_close - 1) * 100

        return Snapshot(
            symbol=symbol.zfill(6),
            name=str(data.get("f58") or symbol),
            asset_type=asset_type,
            price=price,
            change_pct=change_pct or 0.0,
            open=_num(data.get("f46")),
            high=_num(data.get("f44")),
            low=_num(data.get("f45")),
            prev_close=prev_close,
            volume=_num(data.get("f47")),
            amount=_num(data.get("f48")),
            volume_ratio=_num(data.get("f50")),
            updated_at=datetime.now(SHANGHAI).isoformat(timespec="seconds"),
            source="eastmoney",
        )

    def _tencent_snapshot(self, symbol: str, asset_type: str) -> Snapshot:
        code = _tencent_code(symbol, asset_type)
        url = "https://qt.gtimg.cn/q=" + code
        response = self.session.get(
            url,
            timeout=self.timeout,
            headers={"Referer": "https://gu.qq.com/"},
        )
        response.raise_for_status()
        response.encoding = "gb18030"
        text = response.text.strip()
        if '="' not in text:
            raise RuntimeError(f"腾讯行情返回格式异常: {text[:80]}")
        raw = text.split('="', 1)[1].rsplit('"', 1)[0]
        parts = raw.split("~")
        if len(parts) < 35:
            raise RuntimeError(f"腾讯行情字段不足: {len(parts)}")

        price = _num(parts[3], 0.0) or 0.0
        prev_close = _num(parts[4])
        change_pct = _num(parts[32])
        if change_pct is None and prev_close not in (None, 0) and price:
            change_pct = (price / prev_close - 1) * 100

        return Snapshot(
            symbol=symbol.zfill(6),
            name=parts[1] or symbol,
            asset_type=asset_type,
            price=price,
            change_pct=change_pct or 0.0,
            open=_num(parts[5]),
            high=_num(parts[33]),
            low=_num(parts[34]),
            prev_close=prev_close,
            volume=_num(parts[6]),
            amount=None,
            volume_ratio=None,
            updated_at=parts[30] if len(parts) > 30 and parts[30] else datetime.now(SHANGHAI).isoformat(timespec="seconds"),
            source="tencent",
        )

    # 保留旧的全市场表方法，便于后续诊断或本地使用；主监控不再依赖它。
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
                source="akshare-eastmoney-table",
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
                source="akshare-eastmoney-table",
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
                source="akshare-eastmoney-table",
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
