"""Dashboard runtime cho Day 13 — đọc data/logs.jsonl, hiển thị đúng 6 panel
theo contract trong config/dashboard.yaml.

Chạy: streamlit run scripts/dashboard_app.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.metrics import percentile

LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
DASHBOARD_CONFIG_PATH = REPO_ROOT / "config" / "dashboard.yaml"


def load_dashboard_config() -> dict:
    payload = yaml.safe_load(DASHBOARD_CONFIG_PATH.read_text(encoding="utf-8"))
    return payload["dashboard"]


def load_events(window_minutes: int) -> list[dict]:
    if not LOG_PATH.exists():
        return []
    events = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not events:
        return []
    latest = max(datetime.fromisoformat(e["ts"].replace("Z", "+00:00")) for e in events)
    cutoff = latest - timedelta(minutes=window_minutes)
    return [
        e
        for e in events
        if datetime.fromisoformat(e["ts"].replace("Z", "+00:00")) >= cutoff
    ]


def minute_bucket(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt.replace(second=0, microsecond=0)


def threshold_status(value: float, threshold: dict) -> tuple[str, bool]:
    op = threshold["operator"]
    limit = threshold["value"]
    ok = value <= limit if op == "lte" else value >= limit
    symbol = "≤" if op == "lte" else "≥"
    return f"Ngưỡng: {symbol} {limit} {threshold.get('aggregation', '')}", ok


def panel_config(panels: list[dict], panel_id: str) -> dict:
    return next(p for p in panels if p["id"] == panel_id)


def main() -> None:
    config = load_dashboard_config()
    panels = config["panels"]
    window_minutes = config["time_range_minutes"]
    refresh_seconds = config["refresh_seconds"]

    st.set_page_config(page_title=config["title"], layout="wide")
    st.markdown(f'<meta http-equiv="refresh" content="{refresh_seconds}">', unsafe_allow_html=True)
    st.title(config["title"])
    st.caption(
        f"Nguồn: data/logs.jsonl · Time range: {window_minutes} phút · "
        f"Auto-refresh: {refresh_seconds}s"
    )

    events = load_events(window_minutes)
    if not events:
        st.warning("Chưa có data/logs.jsonl hoặc không có event nào trong time range. "
                    "Chạy `uvicorn app.main:app` + `python scripts/load_test.py` trước.")
        return

    received = [e for e in events if e["event"] == "request_received"]
    failed = [e for e in events if e["event"] == "request_failed"]
    responses = [e for e in events if e["event"] == "response_sent"]

    row1 = st.columns(3)
    row2 = st.columns(3)

    # 1. Latency percentiles
    with row1[0]:
        p = panel_config(panels, "latency")
        st.subheader(p["title"])
        latencies = [e["latency_ms"] for e in responses if "latency_ms" in e]
        p50, p95, p99 = percentile(latencies, 50), percentile(latencies, 95), percentile(latencies, 99)
        st.metric("P95 latency (ms)", p95)
        st.caption(f"P50: {p50} ms · P99: {p99} ms")
        note, ok = threshold_status(p95, p["threshold"])
        (st.success if ok else st.error)(note)
        by_min = defaultdict(list)
        for e in responses:
            by_min[minute_bucket(e["ts"])].append(e.get("latency_ms", 0))
        if by_min:
            df = pd.DataFrame(
                {"p95_ms": [percentile(v, 95) for v in by_min.values()]},
                index=sorted(by_min.keys()),
            )
            st.line_chart(df)

    # 2. Traffic
    with row1[1]:
        p = panel_config(panels, "traffic")
        st.subheader(p["title"])
        st.metric("Tổng request", len(received))
        rate_per_min = len(received) / max(window_minutes, 1)
        st.caption(f"~{rate_per_min:.2f} request/phút")
        note, ok = threshold_status(rate_per_min, p["threshold"])
        (st.success if ok else st.error)(note)
        by_min = Counter(minute_bucket(e["ts"]) for e in received)
        if by_min:
            df = pd.DataFrame({"requests": list(by_min.values())}, index=sorted(by_min.keys()))
            st.bar_chart(df)

    # 3. Errors
    with row1[2]:
        p = panel_config(panels, "errors")
        st.subheader(p["title"])
        error_rate_pct = round(len(failed) / len(received) * 100, 2) if received else 0.0
        st.metric("Error rate (%)", error_rate_pct)
        note, ok = threshold_status(error_rate_pct, p["threshold"])
        (st.success if ok else st.error)(note)
        breakdown = Counter(e.get("error_type", "unknown") for e in failed)
        if breakdown:
            st.bar_chart(pd.DataFrame({"count": breakdown.values()}, index=breakdown.keys()))
        else:
            st.caption("Không có lỗi trong time range.")

    # 4. Cost
    with row2[0]:
        p = panel_config(panels, "cost")
        st.subheader(p["title"])
        costs = [e["cost_usd"] for e in responses if "cost_usd" in e]
        total_cost = round(sum(costs), 4)
        st.metric("Tổng cost (USD)", total_cost)
        note, ok = threshold_status(total_cost, p["threshold"])
        (st.success if ok else st.error)(note)
        by_min = defaultdict(float)
        for e in responses:
            by_min[minute_bucket(e["ts"])] += e.get("cost_usd", 0.0)
        if by_min:
            st.line_chart(pd.DataFrame({"cost_usd": list(by_min.values())}, index=sorted(by_min.keys())))

    # 5. Tokens
    with row2[1]:
        p = panel_config(panels, "tokens")
        st.subheader(p["title"])
        tokens_in = sum(e.get("tokens_in", 0) for e in responses)
        tokens_out = sum(e.get("tokens_out", 0) for e in responses)
        st.metric("Tokens in", tokens_in)
        st.metric("Tokens out", tokens_out)
        note, ok = threshold_status(tokens_in + tokens_out, p["threshold"])
        (st.success if ok else st.error)(note)
        st.bar_chart(pd.DataFrame({"tokens": [tokens_in, tokens_out]}, index=["in", "out"]))

    # 6. Quality
    with row2[2]:
        p = panel_config(panels, "quality")
        st.subheader(p["title"])
        scores = [e["quality_score"] for e in responses if "quality_score" in e]
        avg_quality = round(sum(scores) / len(scores), 4) if scores else 0.0
        st.metric("Quality proxy (0-1)", avg_quality)
        note, ok = threshold_status(avg_quality, p["threshold"])
        (st.success if ok else st.error)(note)
        by_min = defaultdict(list)
        for e in responses:
            by_min[minute_bucket(e["ts"])].append(e.get("quality_score", 0.0))
        if by_min:
            avg_by_min = {k: sum(v) / len(v) for k, v in by_min.items()}
            st.line_chart(pd.DataFrame({"quality_score": list(avg_by_min.values())}, index=sorted(avg_by_min.keys())))


if __name__ == "__main__":
    main()
