# Entrypoint: start APScheduler and execute monitoring runs on the configured interval.

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

import config
from news_agent.agent import run_monitoring_once
from news_agent.logging_utils import configure_logging

MONITORING_JOB_ID = "monitoring_run"


def _run_scheduled_job() -> None:
    run_id = run_monitoring_once()
    logging.info("Scheduled monitoring run completed: run_id=%s", run_id)


def create_scheduler() -> BlockingScheduler:
    configure_logging()
    scheduler = BlockingScheduler()
    scheduler.add_job(
        _run_scheduled_job,
        trigger=IntervalTrigger(hours=config.SCHEDULE_INTERVAL_HOURS),
        id=MONITORING_JOB_ID,
        max_instances=1,
        coalesce=True,
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc),
    )
    return scheduler


def main() -> None:
    scheduler = create_scheduler()
    logging.info(
        "Starting scheduler with interval=%s hour(s)",
        config.SCHEDULE_INTERVAL_HOURS,
    )
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logging.info("Scheduler stopped")
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
