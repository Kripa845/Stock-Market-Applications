"""
Subprocess-based spider runner.

WHY SUBPROCESS INSTEAD OF CrawlerProcess/CrawlerRunner?
--------------------------------------------------------
The pipelines in this project call `django.setup()` and run ORM
operations through Twisted's `deferToThread`, which assumes Scrapy owns
its own reactor for the lifetime of one `scrapy crawl` process. Trying
to start a second Scrapy reactor inside a long-lived Celery worker
process (which already has its own event loop / prefork model) is a
well-known source of "ReactorNotRestartable" and asyncio-related
crashes.

Shelling out to `scrapy crawl <spider>` gives every crawl run a clean
process and a clean reactor, exactly like running it by hand from the
terminal — the only difference is that Celery beat / a cron job is the
one pressing "enter" instead of a person. This is also the reason the
official Scrapy docs recommend `scrapyd` or a subprocess call for
running spiders from other long-lived Python processes.

Both apps/crawler_runs/tasks.py (Celery) and the `run_crawl` management
command (cron / manual) call into this module so there is exactly one
place that knows how to invoke a spider.
"""

import shlex
import subprocess
from pathlib import Path

# Backend/crawlers  (the Scrapy project root, i.e. where scrapy.cfg lives)
CRAWLER_PROJECT_DIR = Path(__file__).resolve().parent

# All spiders this project ships. Kept as a single source of truth so
# Celery tasks, the management command, and the beat schedule can't
# silently drift from what actually exists in crawlers/spiders/.
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
    """
    Run `scrapy crawl <spider_name>` as a subprocess.

    spider_args: dict of `-a key=value` arguments forwarded to the
                 spider's __init__ (e.g. {"max_articles": 30}).
    timeout:     hard ceiling in seconds so one hung crawl can't block
                 the whole scheduled run forever (default 30 minutes).

    Returns a SpiderRunResult. Never raises for a *crawl* failure
    (non-zero exit, timeout, etc.) — callers decide how to treat that,
    which keeps one bad portal from taking down the rest of a
    scheduled run. Programmer errors (bad spider_args) still raise.
    """

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
    """
    Run several spiders back to back, continuing past individual
    failures so one broken portal doesn't stop the rest of the run.
    Returns a list of SpiderRunResult, one per spider.
    """

    return [
        run_spider(name, spider_args=spider_args, timeout=timeout)
        for name in spider_names
    ]


def _cli_preview(command):
    """Human-readable form of a command list, for logging only."""
    return " ".join(shlex.quote(part) for part in command)
