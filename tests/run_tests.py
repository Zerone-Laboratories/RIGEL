#!/usr/bin/env python3
"""
RIGEL Test Runner — executes the test suite, writes a CSV summary, and produces
a detailed execution log.

Outputs (placed in tests/output/):
    test_results.csv   – one row per test with status / duration / error info
    test_execution.log – timestamped step-by-step execution log
"""

import csv
import logging
import os
import sys
import time
from datetime import datetime, timezone

import pytest


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(TESTS_DIR, "output")
CSV_PATH = os.path.join(OUTPUT_DIR, "test_results.csv")
LOG_PATH = os.path.join(OUTPUT_DIR, "test_execution.log")


def setup_logging(log_path: str) -> logging.Logger:
    """Configure dual-output logging: console + file."""
    logger = logging.getLogger("rigel_test_runner")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    # File handler — detailed
    fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    # Console handler — info and above
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


class CsvResultsCollector:
    """Pytest plugin that collects per-test results for CSV export."""

    def __init__(self):
        self.results: list[dict] = []
        self._start_times: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Hook: test call begins
    # ------------------------------------------------------------------
    def pytest_runtest_protocol(self, item, nextitem):
        self._start_times[item.nodeid] = time.time()
        return None  # let other plugins / default runner continue

    # ------------------------------------------------------------------
    # Hook: test finished
    # ------------------------------------------------------------------
    def pytest_runtest_logreport(self, report):
        if report.when != "call":
            return
        duration = time.time() - self._start_times.pop(report.nodeid, time.time())

        status = "passed"
        message = ""
        if report.failed:
            status = "failed"
            message = report.longreprtext if hasattr(report, "longreprtext") else str(report.longrepr)
        elif report.skipped:
            status = "skipped"
            message = str(report.longrepr) if report.longrepr else ""

        self.results.append({
            "test_name": report.nodeid.split("::")[-1],
            "test_path": report.nodeid,
            "status": status,
            "duration_sec": round(duration, 4),
            "message": message[:500],  # truncate very long errors
        })


def write_csv(results: list[dict], path: str, logger: logging.Logger):
    """Write the collected results to a CSV file."""
    fieldnames = ["test_name", "test_path", "status", "duration_sec", "message"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    logger.info(f"CSV written: {path}  ({len(results)} rows)")


def run() -> int:
    """Run all tests, collect results, write outputs."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    logger = setup_logging(LOG_PATH)
    start_time = datetime.now(timezone.utc)
    logger.info("=" * 70)
    logger.info("RIGEL Test Suite Runner — started at %s (UTC)", start_time.isoformat())
    logger.info("Tests directory : %s", TESTS_DIR)
    logger.info("Output directory: %s", OUTPUT_DIR)
    logger.info("Python          : %s", sys.version.split()[0])
    logger.info("=" * 70)

    # ------------------------------------------------------------------
    # Collect results via custom plugin
    # ------------------------------------------------------------------
    collector = CsvResultsCollector()

    logger.info("Discovering and running tests…")
    exit_code = pytest.main(
        [
            TESTS_DIR,
            "-v",                          # verbose
            "--tb=long",                   # long tracebacks in stdout
            "--color=yes",
            "-p", "no:cacheprovider",      # skip cache to keep results fresh
        ],
        plugins=[collector],
    )

    # ------------------------------------------------------------------
    # Summaries
    # ------------------------------------------------------------------
    total = len(collector.results)
    passed = sum(1 for r in collector.results if r["status"] == "passed")
    failed = sum(1 for r in collector.results if r["status"] == "failed")
    skipped = sum(1 for r in collector.results if r["status"] == "skipped")
    total_duration = sum(r["duration_sec"] for r in collector.results)

    logger.info("")
    logger.info("=" * 70)
    logger.info("RESULTS SUMMARY")
    logger.info("=" * 70)
    logger.info("  Total  : %d", total)
    logger.info("  Passed : %d", passed)
    logger.info("  Failed : %d", failed)
    logger.info("  Skipped: %d", skipped)
    logger.info("  Duration: %.2f s", total_duration)

    if failed:
        logger.warning("  FAILURES:")
        for r in collector.results:
            if r["status"] == "failed":
                logger.warning("    - %s", r["test_path"])
                logger.warning("      %s", r["message"][:200])

    # ------------------------------------------------------------------
    # Write CSV
    # ------------------------------------------------------------------
    write_csv(collector.results, CSV_PATH, logger)

    end_time = datetime.now(timezone.utc)
    logger.info("")
    logger.info("Test run completed at %s (UTC)", end_time.isoformat())
    logger.info("Pytest exit code: %d", exit_code)
    logger.info("Log file : %s", LOG_PATH)
    logger.info("CSV file : %s", CSV_PATH)

    # Also print a one-line status to stderr so the caller can parse it
    print(
        f"STATUS: {passed}/{total} passed, {failed} failed, {skipped} skipped "
        f"({total_duration:.1f}s)  CSV={CSV_PATH}  LOG={LOG_PATH}",
        file=sys.stderr,
    )

    return exit_code


if __name__ == "__main__":
    sys.exit(run())
