# Unit tests for news_agent/logging_utils.py (implemented in Step 7).

import config
from news_agent.logging_utils import log_feed_warning, log_global_failure


def test_log_global_failure_writes_timestamp_run_id_and_error(tmp_path, monkeypatch):
    failure_log = tmp_path / "failures.log"
    monkeypatch.setattr(config, "FAILURE_LOG_PATH", str(failure_log))

    log_global_failure(7, "database is locked")

    content = failure_log.read_text()
    assert "run_id=7" in content
    assert "error=database is locked" in content
    assert "T" in content.split()[0]


def test_log_global_failure_uses_unknown_run_id_when_missing(tmp_path, monkeypatch):
    failure_log = tmp_path / "failures.log"
    monkeypatch.setattr(config, "FAILURE_LOG_PATH", str(failure_log))

    log_global_failure(None, "unexpected crash")

    content = failure_log.read_text()
    assert "run_id=unknown" in content
    assert "error=unexpected crash" in content


def test_log_feed_warning_does_not_write_failure_log(tmp_path, monkeypatch, caplog):
    failure_log = tmp_path / "failures.log"
    monkeypatch.setattr(config, "FAILURE_LOG_PATH", str(failure_log))

    log_feed_warning("https://example.com/feed.xml", "Feed unreachable")

    assert not failure_log.exists()
    assert "Feed unreachable" in caplog.text
