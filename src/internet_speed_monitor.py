#!/usr/bin/env python3

import argparse
import csv
import html
import time
from datetime import datetime
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


def generate_html_report(csv_file: Path, html_file: Path) -> None:
    ensure_csv_exists(csv_file)
    html_file.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_file)

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
        stats = build_download_stats(ok_df)

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
        <section class="summary">
            <h2>Summary</h2>
            <div class="cards">
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
                    <div class="value">{stats["samples"]}</div>
                </div>
            </div>
        </section>

        <section>
            <h2>Download Statistics</h2>
            <div class="cards">
                <div class="card">
                    <div class="label">Average download</div>
                    <div class="value">{stats["average"]} Mbps</div>
                </div>
                <div class="card">
                    <div class="label">Median download</div>
                    <div class="value">{stats["median"]} Mbps</div>
                </div>
                <div class="card">
                    <div class="label">Minimum download</div>
                    <div class="value">{stats["minimum"]} Mbps</div>
                </div>
                <div class="card">
                    <div class="label">Maximum download</div>
                    <div class="value">{stats["maximum"]} Mbps</div>
                </div>
                <div class="card">
                    <div class="label">Latest download</div>
                    <div class="value">{stats["latest"]} Mbps</div>
                </div>
            </div>
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
            margin: 32px;
            background: #f7f7f7;
            color: #222;
        }}

        h1, h2 {{
            color: #111;
        }}

        section {{
            background: #fff;
            padding: 24px;
            margin-bottom: 24px;
            border-radius: 14px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        }}

        .cards {{
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
        }}

        .card {{
            background: #f1f1f1;
            padding: 18px;
            border-radius: 12px;
            min-width: 180px;
        }}

        .label {{
            font-size: 14px;
            color: #555;
        }}

        .value {{
            font-size: 28px;
            font-weight: bold;
            margin-top: 8px;
        }}

        textarea {{
            width: 100%;
            min-height: 260px;
            font-family: Consolas, monospace;
            font-size: 14px;
            padding: 14px;
            box-sizing: border-box;
        }}

        .data-table {{
            border-collapse: collapse;
            width: 100%;
            font-size: 14px;
        }}

        .data-table th,
        .data-table td {{
            border-bottom: 1px solid #ddd;
            padding: 8px;
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
        generate_html_report(csv_file, html_file)

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

        log(f"Report updated: {html_file}")

        if args.once:
            break

        sleep_seconds = args.interval * 60
        log(f"Sleeping {sleep_seconds} seconds until next cycle")
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
