

import shlex
import subprocess
import sys
from pathlib import Path

CRAWLER_PROJECT_DIR = Path(__file__).resolve().parent


NEWS_SPIDERS = [
    "sharesansar",
    "merolagani",
    "bizmandu",
    "nepsealpha",
    "arthakhabar",
    "fiscalnepal",
]

MARKET_DATA_SPIDERS = [
    "trading_data",
]

FLOORSHEET_SPIDERS = [
    "floorsheet",
]

ALL_SPIDERS = NEWS_SPIDERS + MARKET_DATA_SPIDERS + FLOORSHEET_SPIDERS


class SpiderRunResult:
    def __init__(self, spider_name, returncode, stdout, stderr):
        self.spider_name = spider_name
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    @property
    def ok(self):
        return self.returncode == 0

    def __repr__(self):
        status = "OK" if self.ok else f"FAILED({self.returncode})"
        return f"<SpiderRunResult {self.spider_name} {status}>"


def run_spider(
    spider_name,
    spider_args=None,
    timeout=60 * 30,
    on_process_started=None,
):
    

    if spider_name not in ALL_SPIDERS:
        raise ValueError(
            f"Unknown spider '{spider_name}'. "
            f"Known spiders: {', '.join(ALL_SPIDERS)}"
        )

    command = [sys.executable, "-m", "scrapy", "crawl", spider_name]

    for key, value in (spider_args or {}).items():
        command += ["-a", f"{key}={value}"]

    try:
        process = subprocess.Popen(
            command,
            cwd=str(CRAWLER_PROJECT_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if on_process_started:
            on_process_started(process.pid)

        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            return SpiderRunResult(
                spider_name=spider_name,
                returncode=-1,
                stdout=(stdout or "")[-4000:],
                stderr=(stderr or "")[-4000:]
                + f"\nSpider '{spider_name}' timed out after {timeout}s",
            )

        return SpiderRunResult(
            spider_name=spider_name,
            returncode=process.returncode,
            stdout=(stdout or "")[-4000:],
            stderr=(stderr or "")[-4000:],
        )

    except FileNotFoundError:
        return SpiderRunResult(
            spider_name=spider_name,
            returncode=-2,
            stdout="",
            stderr=(
                "Scrapy is not installed in the Python environment used "
                f"by the worker: {sys.executable}"
            ),
        )


def run_spiders(
    spider_names,
    spider_args=None,
    timeout=60 * 30,
    on_process_started=None,
):


    return [
        run_spider(
            name,
            spider_args=spider_args,
            timeout=timeout,
            on_process_started=on_process_started,
        )
        for name in spider_names
    ]


def _cli_preview(command):
    """Human-readable form of a command list, for logging only."""
    return " ".join(shlex.quote(part) for part in command)
