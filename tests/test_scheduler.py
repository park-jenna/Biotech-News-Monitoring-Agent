# Unit tests for scheduler.py (implemented in Step 8).

import config
from scheduler import MONITORING_JOB_ID, _run_scheduled_job, create_scheduler


def test_create_scheduler_registers_interval_job_with_no_overlap():
    scheduler = create_scheduler()
    job = scheduler.get_job(MONITORING_JOB_ID)

    assert job is not None
    assert job.max_instances == 1
    assert job.coalesce is True
    assert job.trigger.interval.total_seconds() == config.SCHEDULE_INTERVAL_HOURS * 3600


def test_scheduled_job_calls_run_monitoring_once(monkeypatch):
    calls = {"count": 0}

    def fake_run_monitoring_once():
        calls["count"] += 1
        return 42

    monkeypatch.setattr("scheduler.run_monitoring_once", fake_run_monitoring_once)

    _run_scheduled_job()

    assert calls["count"] == 1
