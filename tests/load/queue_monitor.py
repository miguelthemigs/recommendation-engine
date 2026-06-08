"""
tests/load/queue_monitor.py
───────────────────────────
RabbitMQ queue-depth sidecar for load tests.

Polls the Management API every second and writes a CSV row with:
    timestamp_iso, messages_ready, messages_unacked, messages_total, consumers

Run alongside a k6 test:
    python tests/load/queue_monitor.py results/1worker/queue_depth.csv

Stop with Ctrl+C — the CSV is flushed on exit.
"""

from __future__ import annotations

import argparse
import csv
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

DEFAULT_MGMT_URL = "http://localhost:15672"
DEFAULT_VHOST = "/"
DEFAULT_QUEUE = "coldstart_jobs"
DEFAULT_USER = "guest"
DEFAULT_PASS = "guest"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="RabbitMQ queue depth sampler")
    p.add_argument("output", help="CSV output path")
    p.add_argument("--mgmt-url", default=DEFAULT_MGMT_URL)
    p.add_argument("--vhost", default=DEFAULT_VHOST)
    p.add_argument("--queue", default=DEFAULT_QUEUE)
    p.add_argument("--user", default=DEFAULT_USER)
    p.add_argument("--password", default=DEFAULT_PASS)
    p.add_argument("--interval", type=float, default=1.0, help="seconds between samples")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    vhost_encoded = quote(args.vhost, safe="")
    url = f"{args.mgmt_url}/api/queues/{vhost_encoded}/{args.queue}"
    auth = (args.user, args.password)

    stop = {"flag": False}

    def _on_signal(signum, frame):  # noqa: ARG001
        stop["flag"] = True

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    print(f"[monitor] polling {url} every {args.interval}s -> {out_path}", flush=True)
    print("[monitor] press Ctrl+C to stop", flush=True)

    samples = 0
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "timestamp_iso",
            "messages_ready",
            "messages_unacked",
            "messages_total",
            "consumers",
        ])
        fh.flush()

        while not stop["flag"]:
            try:
                resp = requests.get(url, auth=auth, timeout=2.0)
                ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
                if resp.status_code == 200:
                    data = resp.json()
                    writer.writerow([
                        ts,
                        data.get("messages_ready", 0),
                        data.get("messages_unacknowledged", 0),
                        data.get("messages", 0),
                        data.get("consumers", 0),
                    ])
                    samples += 1
                    if samples % 10 == 0:
                        print(
                            f"[monitor] {ts} ready={data.get('messages_ready', 0)} "
                            f"unacked={data.get('messages_unacknowledged', 0)} "
                            f"consumers={data.get('consumers', 0)}",
                            flush=True,
                        )
                elif resp.status_code == 404:
                    writer.writerow([ts, 0, 0, 0, 0])  # queue not yet declared
                else:
                    print(f"[monitor] HTTP {resp.status_code}: {resp.text[:100]}", file=sys.stderr)
            except requests.RequestException as exc:
                print(f"[monitor] request error: {exc}", file=sys.stderr)

            fh.flush()
            time.sleep(args.interval)

    print(f"[monitor] stopped — wrote {samples} samples to {out_path}", flush=True)


if __name__ == "__main__":
    main()
