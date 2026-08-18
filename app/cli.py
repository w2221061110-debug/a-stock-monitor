from __future__ import annotations

import argparse
import json
import time
from datetime import datetime

from .monitor import StockMonitor


def main() -> None:
    parser = argparse.ArgumentParser(description="A股盘中监控")
    parser.add_argument("--interval", type=int, default=30, help="轮询秒数")
    args = parser.parse_args()

    monitor = StockMonitor()
    last_keys: set[tuple[str, str, str]] = set()

    while True:
        try:
            result = monitor.check()
            current_keys: set[tuple[str, str, str]] = set()
            for alert in result["alerts"]:
                key = (
                    str(alert["code"]),
                    str(alert["symbol"]),
                    f"{alert.get('value')}",
                )
                current_keys.add(key)
                if key not in last_keys:
                    print(json.dumps(alert, ensure_ascii=False))

            for error in result.get("errors", []):
                print(
                    f"[{datetime.now().isoformat(timespec='seconds')}] 数据源错误: "
                    f"{error['symbol']} {error['error']}"
                )
            last_keys = current_keys
        except KeyboardInterrupt:
            break
        except Exception as exc:
            print(f"监控失败: {exc}")

        time.sleep(max(args.interval, 5))


if __name__ == "__main__":
    main()
