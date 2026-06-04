# Failure logging helpers: configure logging, log global failures, log feed warnings.

import logging

import config
from news_agent.utils import utc_now_iso


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def log_global_failure(run_id: int | None, error: str) -> None:
    timestamp = utc_now_iso()
    run_part = f"run_id={run_id}" if run_id is not None else "run_id=unknown"
    line = f"{timestamp} {run_part} error={error}\n"
    with open(config.FAILURE_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line)
    logging.error("%s %s", run_part, error)


def log_feed_warning(feed_url: str, message: str) -> None:
    logging.warning("Feed warning for %s: %s", feed_url, message)
