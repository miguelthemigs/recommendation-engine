"""
tests/load/summarize_results.py
────────────────────────────────
Read k6_summary.json + queue_depth.csv from each results sub-folder and emit
markdown tables ready to paste into CYCLE5.md.

Usage:
    python tests/load/summarize_results.py
"""

import csv
import json
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent / "results"
RUNS = ["1worker", "2workers", "3workers"]


def fmt_ms(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.0f}"


def load_summary(run_dir: Path) -> dict | None:
    path = run_dir / "k6_summary.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_queue(run_dir: Path) -> list[dict]:
    path = run_dir / "queue_depth.csv"
    if not path.exists():
        return []
    rows = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            for k in ("messages_ready", "messages_unacked", "messages_total", "consumers"):
                try:
                    row[k] = int(row[k])
                except (KeyError, ValueError):
                    row[k] = 0
            rows.append(row)
    return rows


def extract_metric(summary: dict, key: str) -> dict:
    # k6 v0.50 summary puts stats directly on the metric object (no .values wrapper).
    return ((summary or {}).get("metrics") or {}).get(key, {}) or {}


def per_run_table(summary: dict | None, queue: list[dict]) -> str:
    if not summary:
        return "_(no summary — run not yet executed)_"

    submit = extract_metric(summary, "coldstart_submit_ms")
    e2e = extract_metric(summary, "coldstart_e2e_ms")
    completed = extract_metric(summary, "coldstart_completed").get("count", 0)
    failed = extract_metric(summary, "coldstart_failed").get("count", 0)
    timeouts = extract_metric(summary, "coldstart_timeout").get("count", 0)
    http_failed_rate = extract_metric(summary, "http_req_failed").get("rate", 0.0)
    poll_rate = extract_metric(summary, "poll_success_rate").get("rate", 0.0)

    peak_ready = max((r["messages_ready"] for r in queue), default=0)
    peak_unacked = max((r["messages_unacked"] for r in queue), default=0)
    peak_total = max((r["messages_total"] for r in queue), default=0)

    lines = [
        "**Submit latency (whole run — k6 doesn't bucket by stage automatically):**",
        "",
        "| Metric | p50 | p95 | p99 | min | max |",
        "|---|---|---|---|---|---|",
        f"| `coldstart_submit_ms` | {fmt_ms(submit.get('med'))} | "
        f"{fmt_ms(submit.get('p(95)'))} | {fmt_ms(submit.get('p(99)'))} | "
        f"{fmt_ms(submit.get('min'))} | {fmt_ms(submit.get('max'))} |",
        f"| `coldstart_e2e_ms` | {fmt_ms(e2e.get('med'))} | "
        f"{fmt_ms(e2e.get('p(95)'))} | {fmt_ms(e2e.get('p(99)'))} | "
        f"{fmt_ms(e2e.get('min'))} | {fmt_ms(e2e.get('max'))} |",
        "",
        "**Throughput and outcomes:**",
        "",
        f"- Jobs completed: **{int(completed)}**",
        f"- Jobs failed: **{int(failed)}**",
        f"- Jobs timed out (>60s poll): **{int(timeouts)}**",
        f"- HTTP failure rate: **{http_failed_rate*100:.2f}%**",
        f"- Poll success rate: **{poll_rate*100:.2f}%**",
        "",
        "**Queue depth:**",
        "",
        f"- Peak `messages_ready`: **{peak_ready}**",
        f"- Peak `messages_unacknowledged`: **{peak_unacked}**",
        f"- Peak total in queue: **{peak_total}**",
    ]
    return "\n".join(lines)


def worker_scaling_table() -> str:
    rows = ["| Workers | submit p95 (ms) | e2e p50 (ms) | e2e p95 (ms) | Completed | Failed | Timeouts | Peak queue |",
            "|---|---|---|---|---|---|---|---|"]
    for run in RUNS:
        run_dir = RESULTS_DIR / run
        summary = load_summary(run_dir)
        queue = load_queue(run_dir)
        if not summary:
            n = run.replace("worker", "").replace("s", "")
            rows.append(f"| {n} | — | — | — | — | — | — | — |")
            continue
        submit = extract_metric(summary, "coldstart_submit_ms")
        e2e = extract_metric(summary, "coldstart_e2e_ms")
        completed = int(extract_metric(summary, "coldstart_completed").get("count", 0))
        failed = int(extract_metric(summary, "coldstart_failed").get("count", 0))
        timeouts = int(extract_metric(summary, "coldstart_timeout").get("count", 0))
        peak = max((r["messages_total"] for r in queue), default=0)
        n = run.replace("worker", "").replace("s", "")
        rows.append(
            f"| {n} | {fmt_ms(submit.get('p(95)'))} | "
            f"{fmt_ms(e2e.get('med'))} | {fmt_ms(e2e.get('p(95)'))} | "
            f"{completed} | {failed} | {timeouts} | {peak} |"
        )
    return "\n".join(rows)


def main() -> None:
    print("# Cycle 5 — extracted results\n")
    print("## Worker scaling comparison\n")
    print(worker_scaling_table())
    print()
    for run in RUNS:
        run_dir = RESULTS_DIR / run
        summary = load_summary(run_dir)
        queue = load_queue(run_dir)
        print(f"\n## {run}\n")
        print(per_run_table(summary, queue))


if __name__ == "__main__":
    main()
