import pandas as pd

from app.models import Snapshot
from app.rules import (
    evaluate_index_cross,
    evaluate_limit_open,
    evaluate_quick_move,
    evaluate_relative_strength,
    evaluate_volume_surge,
)


def snap(**kwargs):
    base = dict(
        symbol="600737",
        name="测试标的",
        asset_type="stock",
        price=10.0,
        change_pct=0.0,
        prev_close=9.0,
        high=10.0,
    )
    base.update(kwargs)
    return Snapshot(**base)


def test_index_cross_up():
    s = snap(symbol="000001", name="上证指数", asset_type="index", price=4001.0)
    bars = pd.DataFrame({"收盘": [3998.0, 3999.5, 4001.0]})
    alerts = evaluate_index_cross(s, bars, 4000.0)
    assert alerts and alerts[0].code == "index_cross_up"


def test_quick_drop():
    s = snap(price=9.7)
    bars = pd.DataFrame({"收盘": [10.0, 9.98, 9.95, 9.9, 9.8, 9.7]})
    alerts = evaluate_quick_move(s, bars, 5, 1.5, -1.5)
    assert alerts and alerts[0].code == "quick_drop"


def test_volume_surge():
    s = snap()
    bars = pd.DataFrame({"成交量": [100, 110, 90, 105, 400]})
    alerts = evaluate_volume_surge(s, bars, 20, 2.0)
    assert alerts and alerts[0].code == "volume_surge"


def test_etf_relative_weak():
    etf = snap(
        symbol="512070",
        name="证券保险ETF",
        asset_type="etf",
        change_pct=-1.2,
    )
    index = snap(
        symbol="000001",
        name="上证指数",
        asset_type="index",
        change_pct=0.1,
    )
    alerts = evaluate_relative_strength(etf, index, 1.0)
    assert alerts and alerts[0].code == "etf_relative_weak"


def test_limit_opened():
    s = snap(price=9.85, prev_close=9.0, high=9.90)
    alerts = evaluate_limit_open(s, 10.0, 0.01)
    assert alerts and alerts[0].code == "limit_up_opened"
