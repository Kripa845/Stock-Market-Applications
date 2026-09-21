"""
Scrapy subprocess runner.

Each call to ``run_spider()`` launches a *new* ``scrapy crawl`` subprocess,
waits for it (up to ``timeout`` seconds), and returns a ``SpiderRunResult``.

Platform notes
--------------
Windows:  subprocess.Popen creates a process;  on timeout we call
          process.kill() which sends SIGTERM on Windows (sufficient for
          Scrapy's clean shutdown).

Linux:    We use os.setsid() so Scrapy and any child processes it spawns
          share a process group.  On timeout we send SIGKILL to the whole
          group so no orphan Scrapy reactor threads linger.
"""

import logging
import os
import shlex
import signal
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

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


def _kill_process(process: subprocess.Popen, spider_name: str) -> None:
    """
    Terminate the Scrapy process (and its process group on Linux).

    Safe to call even if the process has already exited.
    """
    try:
        if os.name == "nt":
            # Windows: kill sends CTRL_BREAK / terminates the process.
            process.kill()
        else:
            # Linux: kill the entire process group so reactor threads
            # spawned by Scrapy/asyncio are also terminated.
            try:
                pgid = os.getpgid(process.pid)
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass  # already dead
            except Exception:
                # Fallback: kill just the main process.
                process.kill()
    except Exception:
        logger.exception(
            "Could not terminate Scrapy process for spider '%s'.", spider_name
        )


def run_spider(
    spider_name: str,
    spider_args: dict | None = None,
    timeout: int = 60 * 30,
    on_process_started=None,
) -> SpiderRunResult:
    """
    Run one Scrapy spider in a subprocess.

    Parameters
    ----------
    spider_name:
        Must be in ALL_SPIDERS.
    spider_args:
        Passed as ``-a key=value`` arguments to Scrapy.
    timeout:
        Seconds to wait before killing the process (default 30 min).
    on_process_started:
        Optional callable receiving the PID once the process starts.
    """
    if spider_name not in ALL_SPIDERS:
        raise ValueError(
            f"Unknown spider '{spider_name}'. "
            f"Known spiders: {', '.join(ALL_SPIDERS)}"
        )

    command = [sys.executable, "-m", "scrapy", "crawl", spider_name]

    for key, value in (spider_args or {}).items():
        command += ["-a", f"{key}={value}"]

    logger.info(
        "Launching spider '%s': %s",
        spider_name,
        _cli_preview(command),
    )

    # On Linux use os.setsid so the subprocess gets its own process group.
    popen_kwargs: dict = {
        "cwd": str(CRAWLER_PROJECT_DIR),
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
    }
    if os.name != "nt":
        popen_kwargs["preexec_fn"] = os.setsid

    try:
        process = subprocess.Popen(command, **popen_kwargs)
    except FileNotFoundError:
        return SpiderRunResult(
            spider_name=spider_name,
            returncode=-2,
            stdout="",
            stderr=(
                "Scrapy executable not found. "
                f"Python: {sys.executable}. "
                "Is Scrapy installed in this environment?"
            ),
        )

    if on_process_started:
        try:
            on_process_started(process.pid)
        except Exception:
            logger.exception(
                "on_process_started callback failed for spider '%s'.",
                spider_name,
            )

    # ------------------------------------------------------------------
    # Wait for the process, enforcing the timeout.
    # ------------------------------------------------------------------
    stdout = ""
    stderr = ""

    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        logger.warning(
            "Spider '%s' timed out after %ds — killing process %s.",
            spider_name,
            timeout,
            process.pid,
        )
        _kill_process(process, spider_name)
        # Drain the pipes after kill.
        try:
            stdout, stderr = process.communicate(timeout=10)
        except Exception:
            process.kill()
            stdout = stdout or ""
            stderr = stderr or ""

        return SpiderRunResult(
            spider_name=spider_name,
            returncode=-1,
            stdout=(stdout or "")[-4000:],
            stderr=(
                (stderr or "")[-3000:]
                + f"\n\n[TIMEOUT] Spider '{spider_name}' killed after {timeout}s."
            ),
        )

    return SpiderRunResult(
        spider_name=spider_name,
        returncode=process.returncode,
        stdout=(stdout or "")[-4000:],
        stderr=(stderr or "")[-4000:],
    )


def run_spiders(
    spider_names: list[str],
    spider_args: dict | None = None,
    timeout: int = 60 * 30,
    on_process_started=None,
) -> list[SpiderRunResult]:
    """
    Run a list of spiders *sequentially* and return all results.

    Sequential execution keeps resource usage predictable and means only
    one Scrapy process is alive at a time, avoiding port / file-handle
    contention that can appear when many asyncio reactors start together.
    """
    results = []
    for name in spider_names:
        result = run_spider(
            name,
            spider_args=spider_args,
            timeout=timeout,
            on_process_started=on_process_started,
        )
        results.append(result)
        if not result.ok:
            logger.warning(
                "Spider '%s' finished with errors (exit=%s); "
                "continuing with remaining spiders.",
                name,
                result.returncode,
            )
    return results


def _cli_preview(command: list[str]) -> str:
    """Human-readable shell-quoted form of a command list, for logging only."""
    return " ".join(shlex.quote(part) for part in command)
