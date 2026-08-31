

import shlex
import subprocess
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


def run_spider(spider_name, spider_args=None, timeout=60 * 30):
    

    if spider_name not in ALL_SPIDERS:
        raise ValueError(
            f"Unknown spider '{spider_name}'. "
            f"Known spiders: {', '.join(ALL_SPIDERS)}"
        )

    command = ["scrapy", "crawl", spider_name]

    for key, value in (spider_args or {}).items():
        command += ["-a", f"{key}={value}"]

    try:
        completed = subprocess.run(
            command,
            cwd=str(CRAWLER_PROJECT_DIR),
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        return SpiderRunResult(
            spider_name=spider_name,
            returncode=completed.returncode,
            stdout=completed.stdout[-4000:],
            stderr=completed.stderr[-4000:],
        )

    except subprocess.TimeoutExpired as exc:
        return SpiderRunResult(
            spider_name=spider_name,
            returncode=-1,
            stdout=(exc.stdout or "")[-4000:] if exc.stdout else "",
            stderr=f"Spider '{spider_name}' timed out after {timeout}s",
        )

    except FileNotFoundError:
        return SpiderRunResult(
            spider_name=spider_name,
            returncode=-2,
            stdout="",
            stderr=(
                "`scrapy` executable not found on PATH. Is Scrapy "
                "installed in this environment/venv?"
            ),
        )


def run_spiders(spider_names, spider_args=None, timeout=60 * 30):


    return [
        run_spider(name, spider_args=spider_args, timeout=timeout)
        for name in spider_names
    ]


def _cli_preview(command):
    """Human-readable form of a command list, for logging only."""
    return " ".join(shlex.quote(part) for part in command)
