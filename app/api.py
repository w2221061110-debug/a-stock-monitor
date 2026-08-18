from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from .monitor import StockMonitor


app = FastAPI(
    title="A Stock Monitor",
    version="0.1.0",
    description="A股盘中行情与条件监控 HTTP API",
)
monitor = StockMonitor()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/monitor/watchlist")
def watchlist() -> dict:
    return {
        "index": monitor.config["index"],
        "watchlist": monitor.watchlist,
        "rules": monitor.config["rules"],
    }


@app.get("/quote/{symbol}")
def quote(
    symbol: str,
    asset_type: str = Query(pattern="^(stock|etf|index)$"),
) -> dict:
    try:
        return monitor.quote(symbol, asset_type).to_dict()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/monitor/check")
def check() -> dict:
    try:
        return monitor.check()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
