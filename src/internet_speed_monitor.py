#!/usr/bin/env python3

import argparse
import csv
import html
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.offline import plot

import speedtest


DEFAULT_CSV_FILE = "internet_speed_results.csv"
DEFAULT_HTML_FILE = "internet_speed_report.html"

CSV_COLUMNS = [
    "timestamp",
    "ping_ms",
    "download_mbps",
    "upload_mbps",
    "server_sponsor",
    "server_name",
    "server_country",
    "server_host",
    "error",
]


def now_as_string() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_csv_exists(csv_file: Path) -> None:
    if not csv_file.exists():
        with csv_file.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()


def run_speed_test() -> dict:
    timestamp = now_as_string()

    try:
        st = speedtest.Speedtest()
        st.get_best_server()

        download_bps = st.download()
        upload_bps = st.upload()
        results = st.results.dict()

        server = results.get("server", {})

        return {
            "timestamp": timestamp,
            "ping_ms": round(results.get("ping", 0), 2),
            "download_mbps": round(download_bps / 1_000_000, 2),
            "upload_mbps": round(upload_bps / 1_000_000, 2),
            "server_sponsor": server.get("sponsor", ""),
            "server_name": server.get("name", ""),
            "server_country": server.get("country", ""),
            "server_host": server.get("host", ""),
            "error": "",
        }

    except Exception as exc:
        return {
            "timestamp": timestamp,
            "ping_ms": "",
            "download_mbps": "",
            "upload_mbps": "",
            "server_sponsor": "",
            "server_name": "",
            "server_country": "",
            "server_host": "",
            "error": str(exc),
        }


def append_result(csv_file: Path, result: dict) -> None:
    ensure_csv_exists(csv_file)

    with csv_file.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writerow(result)


def build_analysis_prompt(csv_file: Path) -> str:
    return f"""
נתחי לי את נתוני מהירות האינטרנט המצורפים.

אני רוצה שתבדקי:
1. האם יש ירידה קבועה במהירות בשעות מסוימות.
2. האם יש הבדל בין הורדה להעלאה.
3. האם יש חריגות משמעותיות.
4. האם הפינג יציב.
5. האם נראה שיש בעיית ספק, תשתית, Wi-Fi או עומס מקומי.
6. מהן ההמלצות המעשיות לשיפור.

הקובץ שמכיל את הנתונים הוא:
{csv_file.name}

אנא החזירי:
- סיכום קצר.
- ממצאים עיקריים.
- שעות בעייתיות אם קיימות.
- המלצות פעולה מסודרות.
""".strip()


def generate_html_report(csv_file: Path, html_file: Path) -> None:
    ensure_csv_exists(csv_file)

    df = pd.read_csv(csv_file)

    if df.empty:
        body = "<p>No data yet.</p>"
    else:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

        numeric_columns = ["ping_ms", "download_mbps", "upload_mbps"]
        for col in numeric_columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        ok_df = df[df["error"].fillna("") == ""].copy()

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
                    <div class="label">Total tests</div>
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
            min-width: 160px;
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

    args = parser.parse_args()

    csv_file = Path(args.csv)
    html_file = Path(args.html)

    ensure_csv_exists(csv_file)

    while True:
        print(f"[{now_as_string()}] Running speed test...")

        result = run_speed_test()
        append_result(csv_file, result)
        generate_html_report(csv_file, html_file)

        if result["error"]:
            print(f"[{now_as_string()}] Test failed: {result['error']}")
        else:
            print(
                f"[{now_as_string()}] "
                f"Download: {result['download_mbps']} Mbps, "
                f"Upload: {result['upload_mbps']} Mbps, "
                f"Ping: {result['ping_ms']} ms"
            )

        print(f"[{now_as_string()}] Report updated: {html_file}")

        if args.once:
            break

        sleep_seconds = args.interval * 60
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()