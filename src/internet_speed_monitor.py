#!/usr/bin/env python3

import argparse
import csv
import html
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.offline import plot

import speedtest


DEFAULT_CSV_FILE = "Outputs/internet_speed_results.csv"
DEFAULT_HTML_FILE = "Outputs/internet_speed_report.html"

MIN_DOWNLOAD_MBPS = 100.0
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_SLEEP_SECONDS = 10

DEFAULT_RECENT_HOURS = 24
DEFAULT_ALERT_MIN_DOWNLOAD = 150.0
DEFAULT_ALERT_CONSECUTIVE_LOW = 6
DEFAULT_ALERT_ACTIVE_START = 7
DEFAULT_ALERT_ACTIVE_END = 23

CSV_COLUMNS = [
    "timestamp",
    "attempt",
    "max_attempts",
    "ping_ms",
    "download_mbps",
    "upload_mbps",
    "server_sponsor",
    "server_name",
    "server_country",
    "server_host",
    "server_distance_km",
    "server_latency_ms",
    "retry_reason",
    "error",
]


def now_as_string() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    print(f"[{now_as_string()}] {message}", flush=True)


def ensure_csv_exists(csv_file: Path) -> None:
    csv_file.parent.mkdir(parents=True, exist_ok=True)

    if not csv_file.exists():
        with csv_file.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()


def normalize_result_for_csv(result: dict[str, Any]) -> dict[str, Any]:
    return {column: result.get(column, "") for column in CSV_COLUMNS}


def run_speed_test_once(attempt: int, max_attempts: int) -> dict[str, Any]:
    timestamp = now_as_string()

    log(f"Starting speed test attempt {attempt}/{max_attempts}")

    try:
        st = speedtest.Speedtest()

        log("Loading speedtest server list")
        st.get_servers()

        log("Selecting best server using speedtest-cli latency-based selection")
        best_server = st.get_best_server()

        server_sponsor = best_server.get("sponsor", "")
        server_name = best_server.get("name", "")
        server_country = best_server.get("country", "")
        server_host = best_server.get("host", "")
        server_distance_km = best_server.get("d", "")
        server_latency_ms = best_server.get("latency", "")

        log(
            "Selected server: "
            f"sponsor='{server_sponsor}', "
            f"name='{server_name}', "
            f"country='{server_country}', "
            f"host='{server_host}', "
            f"distance_km='{server_distance_km}', "
            f"latency_ms='{server_latency_ms}'"
        )
        log(
            "Best server explanation: speedtest-cli selects the best server "
            "mainly by measured latency from the available server list."
        )

        log("Running download test")
        download_bps = st.download()

        log("Running upload test")
        upload_bps = st.upload()

        results = st.results.dict()
        ping_ms = round(float(results.get("ping", 0)), 2)
        download_mbps = round(download_bps / 1_000_000, 2)
        upload_mbps = round(upload_bps / 1_000_000, 2)

        log(
            "Attempt result: "
            f"download={download_mbps} Mbps, "
            f"upload={upload_mbps} Mbps, "
            f"ping={ping_ms} ms"
        )

        retry_reason = ""
        if download_mbps < MIN_DOWNLOAD_MBPS:
            retry_reason = (
                "download_mbps below threshold: "
                f"{download_mbps} < {MIN_DOWNLOAD_MBPS}"
            )

        return {
            "timestamp": timestamp,
            "attempt": attempt,
            "max_attempts": max_attempts,
            "ping_ms": ping_ms,
            "download_mbps": download_mbps,
            "upload_mbps": upload_mbps,
            "server_sponsor": server_sponsor,
            "server_name": server_name,
            "server_country": server_country,
            "server_host": server_host,
            "server_distance_km": server_distance_km,
            "server_latency_ms": server_latency_ms,
            "retry_reason": retry_reason,
            "error": "",
        }

    except Exception as exc:
        error_message = str(exc)
        log(f"Attempt failed with error: {error_message}")

        return {
            "timestamp": timestamp,
            "attempt": attempt,
            "max_attempts": max_attempts,
            "ping_ms": "",
            "download_mbps": "",
            "upload_mbps": "",
            "server_sponsor": "",
            "server_name": "",
            "server_country": "",
            "server_host": "",
            "server_distance_km": "",
            "server_latency_ms": "",
            "retry_reason": "speed test error",
            "error": error_message,
        }


def should_retry(result: dict[str, Any]) -> bool:
    if result.get("error"):
        return True

    retry_reason = str(result.get("retry_reason", "")).strip()
    return bool(retry_reason)


def run_speed_test_with_retries(
    max_attempts: int,
    retry_sleep_seconds: int,
) -> dict[str, Any]:
    last_result: dict[str, Any] = {}

    for attempt in range(1, max_attempts + 1):
        last_result = run_speed_test_once(
            attempt=attempt,
            max_attempts=max_attempts,
        )

        if not should_retry(last_result):
            log("Attempt accepted")
            return last_result

        if attempt < max_attempts:
            log(
                f"Retry required: {last_result.get('retry_reason')}. "
                f"Sleeping {retry_sleep_seconds} seconds before next attempt."
            )
            time.sleep(retry_sleep_seconds)
        else:
            log("Maximum attempts reached. Saving last result.")

    return last_result


def append_result(csv_file: Path, result: dict[str, Any]) -> None:
    ensure_csv_exists(csv_file)

    with csv_file.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writerow(normalize_result_for_csv(result))


def build_analysis_prompt(csv_file: Path) -> str:
    return f"""
נתחי לי את נתוני מהירות האינטרנט המצורפים.

אני רוצה שתבדקי:
1. האם יש ירידה קבועה במהירות ההורדה בשעות מסוימות.
2. האם יש הבדל משמעותי בין הורדה להעלאה.
3. האם יש חריגות משמעותיות במהירות ההורדה.
4. האם הפינג יציב.
5. האם נראה שיש בעיית ספק, תשתית, Wi-Fi או עומס מקומי.
6. מהן ההמלצות המעשיות לשיפור.

הקובץ שמכיל את הנתונים הוא:
{csv_file.name}

אנא החזירי:
- סיכום קצר.
- ממצאים עיקריים.
- ממוצע, חציון, מינימום ומקסימום של מהירות ההורדה.
- שעות בעייתיות אם קיימות.
- המלצות פעולה מסודרות.
""".strip()


def format_number(value: Any, digits: int = 2) -> str:
    if pd.isna(value):
        return "N/A"

    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "N/A"


def build_download_stats(ok_df: pd.DataFrame) -> dict[str, str]:
    empty_stats = {
        "samples": "0",
        "average": "N/A",
        "median": "N/A",
        "minimum": "N/A",
        "maximum": "N/A",
        "latest": "N/A",
    }

    if ok_df.empty or "download_mbps" not in ok_df.columns:
        return empty_stats

    download_series = pd.to_numeric(ok_df["download_mbps"], errors="coerce").dropna()

    if download_series.empty:
        return empty_stats

    latest_value = download_series.iloc[-1]

    return {
        "samples": str(int(download_series.count())),
        "average": format_number(download_series.mean()),
        "median": format_number(download_series.median()),
        "minimum": format_number(download_series.min()),
        "maximum": format_number(download_series.max()),
        "latest": format_number(latest_value),
    }


def filter_last_hours(ok_df: pd.DataFrame, hours: int) -> pd.DataFrame:
    if ok_df.empty or "timestamp" not in ok_df.columns:
        return ok_df.copy()

    cutoff_time = datetime.now() - timedelta(hours=hours)
    return ok_df[ok_df["timestamp"] >= cutoff_time].copy()


def count_download_below_threshold(
    ok_df: pd.DataFrame,
    threshold_mbps: float,
) -> int:
    if ok_df.empty or "download_mbps" not in ok_df.columns:
        return 0

    download_series = pd.to_numeric(ok_df["download_mbps"], errors="coerce")
    return int((download_series < threshold_mbps).sum())


def calculate_low_download_streaks(
    ok_df: pd.DataFrame,
    threshold_mbps: float,
    active_start_hour: int = DEFAULT_ALERT_ACTIVE_START,
    active_end_hour: int = DEFAULT_ALERT_ACTIVE_END,
) -> dict[str, int]:
    if ok_df.empty or "timestamp" not in ok_df.columns or "download_mbps" not in ok_df.columns:
        return {
            "current_streak": 0,
            "max_streak": 0,
        }

    sorted_df = ok_df.sort_values("timestamp", ascending=True).copy()
    current_streak = 0
    max_streak = 0

    for _, row in sorted_df.iterrows():
        timestamp = row.get("timestamp")
        download_mbps = row.get("download_mbps")

        if pd.isna(timestamp) or pd.isna(download_mbps):
            current_streak = 0
            continue

        hour = timestamp.hour

        if not (active_start_hour <= hour < active_end_hour):
            current_streak = 0
            continue

        try:
            download_value = float(download_mbps)
        except (TypeError, ValueError):
            current_streak = 0
            continue

        if download_value < threshold_mbps:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0

    return {
        "current_streak": current_streak,
        "max_streak": max_streak,
    }


def generate_html_report(
    csv_file: Path,
    html_file: Path,
    recent_hours: int = DEFAULT_RECENT_HOURS,
    alert_min_download: float = DEFAULT_ALERT_MIN_DOWNLOAD,
    alert_consecutive_low: int = DEFAULT_ALERT_CONSECUTIVE_LOW,
    alert_active_start: int = DEFAULT_ALERT_ACTIVE_START,
    alert_active_end: int = DEFAULT_ALERT_ACTIVE_END,
) -> bool:
    ensure_csv_exists(csv_file)
    html_file.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_file)
    alert_triggered = False

    if df.empty:
        body = "<p>No data yet.</p>"
    else:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

        numeric_columns = [
            "ping_ms",
            "download_mbps",
            "upload_mbps",
            "server_distance_km",
            "server_latency_ms",
        ]

        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        ok_df = df[df["error"].fillna("") == ""].copy()
        overall_stats = build_download_stats(ok_df)

        recent_df = filter_last_hours(ok_df, recent_hours)
        recent_stats = build_download_stats(recent_df)
        recent_below_threshold = count_download_below_threshold(
            recent_df,
            alert_min_download,
        )

        all_streaks = calculate_low_download_streaks(
            ok_df,
            threshold_mbps=alert_min_download,
            active_start_hour=alert_active_start,
            active_end_hour=alert_active_end,
        )
        recent_streaks = calculate_low_download_streaks(
            recent_df,
            threshold_mbps=alert_min_download,
            active_start_hour=alert_active_start,
            active_end_hour=alert_active_end,
        )

        current_low_streak = all_streaks["current_streak"]
        recent_max_low_streak = recent_streaks["max_streak"]
        alert_triggered = current_low_streak > alert_consecutive_low

        alert_status = "ALERT" if alert_triggered else "OK"
        alert_card_class = "card alert-card" if alert_triggered else "card"

        if ok_df.empty:
            graph_html = "<p>No successful speed tests yet.</p>"
        else:
            fig = go.Figure()

            fig.add_trace(
                go.Scatter(
                    x=ok_df["timestamp"],
                    y=ok_df["download_mbps"],
                    mode="lines+markers",
                    name="Download Mbps",
                )
            )

            fig.add_trace(
                go.Scatter(
                    x=ok_df["timestamp"],
                    y=ok_df["upload_mbps"],
                    mode="lines+markers",
                    name="Upload Mbps",
                )
            )

            fig.add_trace(
                go.Scatter(
                    x=ok_df["timestamp"],
                    y=ok_df["ping_ms"],
                    mode="lines+markers",
                    name="Ping ms",
                    yaxis="y2",
                )
            )

            fig.update_layout(
                title="Internet Speed Over Time",
                xaxis_title="Time",
                yaxis=dict(title="Speed Mbps"),
                yaxis2=dict(
                    title="Ping ms",
                    overlaying="y",
                    side="right",
                ),
                legend=dict(orientation="h"),
                hovermode="x unified",
                template="plotly_white",
                margin=dict(l=40, r=40, t=60, b=40),
            )

            graph_html = plot(
                fig,
                include_plotlyjs="cdn",
                output_type="div",
            )

        latest_rows = df.tail(20).sort_values("timestamp", ascending=False)
        latest_table = latest_rows.to_html(index=False, classes="data-table", border=0)

        total_tests = len(df)
        successful_tests = len(df[df["error"].fillna("") == ""])
        failed_tests = total_tests - successful_tests

        prompt_text = html.escape(build_analysis_prompt(csv_file))

        body = f"""
        <section>
            <h2>Total Measurements</h2>
            <div class="cards cards-compact">
                <div class="card">
                    <div class="label">Total saved tests</div>
                    <div class="value">{total_tests}</div>
                </div>
                <div class="card">
                    <div class="label">Successful tests</div>
                    <div class="value">{successful_tests}</div>
                </div>
                <div class="card">
                    <div class="label">Failed tests</div>
                    <div class="value">{failed_tests}</div>
                </div>
                <div class="card">
                    <div class="label">Download samples</div>
                    <div class="value">{overall_stats["samples"]}</div>
                </div>
            </div>
        </section>

        <section>
            <h2>Overall Download Statistics</h2>
            <div class="cards">
                <div class="card">
                    <div class="label">Average download</div>
                    <div class="value">{overall_stats["average"]} Mbps</div>
                </div>
                <div class="card">
                    <div class="label">Median download</div>
                    <div class="value">{overall_stats["median"]} Mbps</div>
                </div>
                <div class="card">
                    <div class="label">Minimum download</div>
                    <div class="value">{overall_stats["minimum"]} Mbps</div>
                </div>
                <div class="card">
                    <div class="label">Maximum download</div>
                    <div class="value">{overall_stats["maximum"]} Mbps</div>
                </div>
                <div class="card">
                    <div class="label">Latest download</div>
                    <div class="value">{overall_stats["latest"]} Mbps</div>
                </div>
            </div>
        </section>

        <section>
            <h2>Last {recent_hours} Hours</h2>
            <div class="cards">
                <div class="card">
                    <div class="label">Successful samples</div>
                    <div class="value">{recent_stats["samples"]}</div>
                </div>
                <div class="card">
                    <div class="label">Average download</div>
                    <div class="value">{recent_stats["average"]} Mbps</div>
                </div>
                <div class="card">
                    <div class="label">Median download</div>
                    <div class="value">{recent_stats["median"]} Mbps</div>
                </div>
                <div class="card">
                    <div class="label">Minimum download</div>
                    <div class="value">{recent_stats["minimum"]} Mbps</div>
                </div>
                <div class="card">
                    <div class="label">Maximum download</div>
                    <div class="value">{recent_stats["maximum"]} Mbps</div>
                </div>
                <div class="card">
                    <div class="label">Latest download</div>
                    <div class="value">{recent_stats["latest"]} Mbps</div>
                </div>
                <div class="card">
                    <div class="label">Below {format_number(alert_min_download, 0)} Mbps</div>
                    <div class="value">{recent_below_threshold}</div>
                </div>
                <div class="card">
                    <div class="label">Max low streak in period</div>
                    <div class="value">{recent_max_low_streak}</div>
                </div>
                <div class="card">
                    <div class="label">Current low streak</div>
                    <div class="value">{current_low_streak}</div>
                </div>
                <div class="{alert_card_class}">
                    <div class="label">Low-speed alert</div>
                    <div class="value">{alert_status}</div>
                </div>
            </div>
            <p class="note">
                Alert rule: more than {alert_consecutive_low} consecutive successful measurements
                below {format_number(alert_min_download, 0)} Mbps between
                {alert_active_start:02d}:00 and {alert_active_end:02d}:00.
            </p>
        </section>

        <section>
            <h2>Speed Graph</h2>
            {graph_html}
        </section>

        <section>
            <h2>Prompt for ChatGPT Analysis</h2>
            <p>Copy this prompt and upload the CSV file to ChatGPT for analysis.</p>
            <textarea readonly>{prompt_text}</textarea>
        </section>

        <section>
            <h2>Latest Results</h2>
            {latest_table}
        </section>
        """

    html_content = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Internet Speed Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 18px;
            background: #f7f7f7;
            color: #222;
        }}

        h1 {{
            color: #111;
            font-size: 26px;
            margin: 0 0 14px 0;
        }}

        h2 {{
            color: #111;
            font-size: 20px;
            margin: 0 0 16px 0;
        }}

        p {{
            font-size: 14px;
            margin: 0 0 14px 0;
        }}

        section {{
            background: #fff;
            padding: 16px;
            margin-bottom: 16px;
            border-radius: 10px;
            box-shadow: 0 1px 8px rgba(0,0,0,0.07);
        }}

        .cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 12px;
            align-items: stretch;
        }}

        .cards-compact {{
            grid-template-columns: repeat(auto-fit, minmax(140px, 180px));
        }}

        .card {{
            background: #f1f1f1;
            padding: 12px;
            border-radius: 9px;
            min-width: 0;
        }}

        .alert-card {{
            background: #ffe0e0;
        }}

        .label {{
            font-size: 12px;
            color: #555;
            line-height: 1.25;
        }}

        .value {{
            font-size: 22px;
            font-weight: bold;
            margin-top: 6px;
            line-height: 1.15;
            white-space: nowrap;
        }}

        .note {{
            margin: 14px 0 0 0;
            color: #555;
            font-size: 12px;
        }}

        textarea {{
            width: 100%;
            min-height: 220px;
            font-family: Consolas, monospace;
            font-size: 13px;
            padding: 12px;
            box-sizing: border-box;
        }}

        .data-table {{
            border-collapse: collapse;
            width: 100%;
            font-size: 13px;
        }}

        .data-table th,
        .data-table td {{
            border-bottom: 1px solid #ddd;
            padding: 6px;
            text-align: left;
        }}

        .data-table th {{
            background: #f0f0f0;
        }}
    </style>
</head>
<body>
    <h1>Internet Speed Report</h1>
    <p>Last generated: {now_as_string()}</p>
    {body}
</body>
</html>
"""

    html_file.write_text(html_content, encoding="utf-8")
    return alert_triggered


def main() -> None:
    global MIN_DOWNLOAD_MBPS

    parser = argparse.ArgumentParser(
        description="Monitor internet speed and generate an HTML report."
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Interval between tests in minutes. Default: 30.",
    )

    parser.add_argument(
        "--csv",
        default=DEFAULT_CSV_FILE,
        help=f"CSV output file. Default: {DEFAULT_CSV_FILE}.",
    )

    parser.add_argument(
        "--html",
        default=DEFAULT_HTML_FILE,
        help=f"HTML report file. Default: {DEFAULT_HTML_FILE}.",
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one test only and exit.",
    )

    parser.add_argument(
        "--min-download",
        type=float,
        default=MIN_DOWNLOAD_MBPS,
        help=f"Minimum accepted download Mbps. Default: {MIN_DOWNLOAD_MBPS}.",
    )

    parser.add_argument(
        "--max-attempts",
        type=int,
        default=DEFAULT_MAX_ATTEMPTS,
        help=f"Maximum attempts per run. Default: {DEFAULT_MAX_ATTEMPTS}.",
    )

    parser.add_argument(
        "--retry-sleep",
        type=int,
        default=DEFAULT_RETRY_SLEEP_SECONDS,
        help=(
            "Seconds to wait before retry after error or low download. "
            f"Default: {DEFAULT_RETRY_SLEEP_SECONDS}."
        ),
    )

    parser.add_argument(
        "--recent-hours",
        type=int,
        default=DEFAULT_RECENT_HOURS,
        help=f"Recent-hours window for the report. Default: {DEFAULT_RECENT_HOURS}.",
    )

    parser.add_argument(
        "--alert-min-download",
        type=float,
        default=DEFAULT_ALERT_MIN_DOWNLOAD,
        help=(
            "Low download threshold for report indicators. "
            f"Default: {DEFAULT_ALERT_MIN_DOWNLOAD} Mbps."
        ),
    )

    parser.add_argument(
        "--alert-consecutive-low",
        type=int,
        default=DEFAULT_ALERT_CONSECUTIVE_LOW,
        help=(
            "Alert when the current low-download streak is greater than this value. "
            f"Default: {DEFAULT_ALERT_CONSECUTIVE_LOW}."
        ),
    )

    parser.add_argument(
        "--alert-active-start",
        type=int,
        default=DEFAULT_ALERT_ACTIVE_START,
        help=(
            "Active alert window start hour, inclusive. "
            f"Default: {DEFAULT_ALERT_ACTIVE_START}."
        ),
    )

    parser.add_argument(
        "--alert-active-end",
        type=int,
        default=DEFAULT_ALERT_ACTIVE_END,
        help=(
            "Active alert window end hour, exclusive. "
            f"Default: {DEFAULT_ALERT_ACTIVE_END}."
        ),
    )

    args = parser.parse_args()

    MIN_DOWNLOAD_MBPS = args.min_download

    csv_file = Path(args.csv)
    html_file = Path(args.html)

    ensure_csv_exists(csv_file)

    while True:
        log("Running internet speed monitor cycle")

        result = run_speed_test_with_retries(
            max_attempts=args.max_attempts,
            retry_sleep_seconds=args.retry_sleep,
        )

        append_result(csv_file, result)
        alert_triggered = generate_html_report(
            csv_file,
            html_file,
            recent_hours=args.recent_hours,
            alert_min_download=args.alert_min_download,
            alert_consecutive_low=args.alert_consecutive_low,
            alert_active_start=args.alert_active_start,
            alert_active_end=args.alert_active_end,
        )

        if result["error"]:
            log(f"Final saved result failed: {result['error']}")
        else:
            log(
                "Final saved result: "
                f"download={result['download_mbps']} Mbps, "
                f"upload={result['upload_mbps']} Mbps, "
                f"ping={result['ping_ms']} ms, "
                f"server={result['server_sponsor']} / {result['server_name']}"
            )

        if alert_triggered:
            log(
                "LOW SPEED ALERT: current low-download streak is greater than "
                f"{args.alert_consecutive_low}; threshold={args.alert_min_download} Mbps; "
                f"active window={args.alert_active_start:02d}:00-{args.alert_active_end:02d}:00"
            )

        log(f"Report updated: {html_file}")

        if args.once:
            break

        sleep_seconds = args.interval * 60
        log(f"Sleeping {sleep_seconds} seconds until next cycle")
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
