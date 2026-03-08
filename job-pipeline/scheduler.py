"""
Scheduler for running job discovery on a schedule.

This script runs the job search daily at 08:00 using the `schedule` library.
Keep this running in the background for automatic job discovery.

Usage:
    python scheduler.py

To stop: Press Ctrl+C
"""

import schedule
import time
import subprocess
import sys
from pathlib import Path
from datetime import datetime


PROJECT_ROOT = Path(__file__).parent


def run_discovery() -> None:
    """Run the job discovery pipeline."""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running daily job search...")
    
    script_path = PROJECT_ROOT / "discovery" / "run_search.py"
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        print(result.stdout)
        if result.stderr:
            print(f"Warnings: {result.stderr}")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Discovery completed successfully")
    except subprocess.CalledProcessError as e:
        print(f"Error running discovery: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
    except Exception as e:
        print(f"Unexpected error: {e}")


def run_scoring() -> None:
    """Run the job scoring after discovery."""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running job scoring...")
    
    script_path = PROJECT_ROOT / "discovery" / "scorer.py"
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        print(result.stdout)
        if result.stderr:
            print(f"Warnings: {result.stderr}")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scoring completed successfully")
    except subprocess.CalledProcessError as e:
        print(f"Error running scoring: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


def daily_job() -> None:
    """Full daily job: discovery then scoring."""
    run_discovery()
    run_scoring()


def main() -> None:
    """Main entry point for the scheduler."""
    print("=" * 60)
    print("Job Pipeline Scheduler")
    print("=" * 60)
    print(f"\nStarted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Scheduled run time: 08:00 daily")
    print("\nPress Ctrl+C to stop the scheduler.\n")
    
    # Schedule the daily job at 08:00
    schedule.every().day.at("08:00").do(daily_job)
    
    # Show next run time
    next_run = schedule.next_run()
    if next_run:
        print(f"Next scheduled run: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
    
    print("\nScheduler is running. Waiting for scheduled time...")
    print("-" * 60)
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        print("\n\nScheduler stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
