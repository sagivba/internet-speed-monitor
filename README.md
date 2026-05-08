# Internet Speed Monitor

Python-based internet speed monitor for WSL/Linux.

The script runs an internet speed test, saves the results to a CSV file, and generates an HTML report with an interactive graph.

## Project Structure
```
internet-speed-monitor/
├── src/
│   └── internet_speed_monitor.py
├── logs/
│   └── cron.log
├── Outputs/
│   ├── internet_speed_results.csv
│   └── internet_speed_report.html
├── speed-monitor-venv/
├── requirements.txt
├── run_speed_test.sh
├── setup_speed_monitor_env.sh
├── cron_example.txt
├── README.md
└── .gitignore
```

## Features

- Download speed monitoring
- Upload speed monitoring
- Ping monitoring
- CSV history file
- HTML report with interactive graph
- Ready for cron scheduling
- Uses a dedicated Python virtual environment

## Project Path

Default project path:

    /home/sagivba-adm/src/internet-speed-monitor

## Setup

    cd /home/sagivba-adm/src/internet-speed-monitor
    chmod +x setup_speed_monitor_env.sh run_speed_test.sh
    ./setup_speed_monitor_env.sh

## Run Manually

    ./run_speed_test.sh

The generated output files will be created under:

    Outputs/

Expected files:

    Outputs/internet_speed_results.csv
    Outputs/internet_speed_report.html

## Run with cron

Edit crontab:

    crontab -e

Add this line to run every 30 minutes:

    */30 * * * * /home/sagivba-adm/src/internet-speed-monitor/run_speed_test.sh >> /home/sagivba-adm/src/internet-speed-monitor/logs/cron.log 2>&1

## Check cron log

    tail -n 50 /home/sagivba-adm/src/internet-speed-monitor/logs/cron.log

## Check CSV data

    tail /home/sagivba-adm/src/internet-speed-monitor/Outputs/internet_speed_results.csv

## Open HTML report from Windows

From Windows Explorer, use:

    \\wsl$\Ubuntu\home\sagivba-adm\src\internet-speed-monitor\Outputs\internet_speed_report.html

If your WSL distribution name is not Ubuntu, check it from PowerShell:

    wsl -l -v

## Files not committed to Git

The following files are local runtime files and should not be committed:

    speed-monitor-venv/
    logs/
    Outputs/

## GitHub initialization

    git init
    git add src/internet_speed_monitor.py requirements.txt setup_speed_monitor_env.sh run_speed_test.sh cron_example.txt README.md .gitignore
    git commit -m "Initial internet speed monitor"
# internet-speed-monitor
