"""
Tests for job_monitor module.

Phase B+: Background job monitoring tests.
"""

import os
import signal
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestIsProcessRunning:
    """Tests for is_process_running function."""

    def test_current_process_is_running(self):
        """Should detect current process as running."""
        from src.infra.job_monitor import is_process_running

        result = is_process_running(os.getpid())
        assert result is True

    def test_invalid_pid_not_running(self):
        """Should return False for invalid PIDs."""
        from src.infra.job_monitor import is_process_running

        assert is_process_running(None) is False
        assert is_process_running(0) is False
        assert is_process_running(-1) is False

    def test_nonexistent_pid_not_running(self):
        """Should return False for nonexistent PID."""
        from src.infra.job_monitor import is_process_running

        # Use a very high PID that's unlikely to exist
        result = is_process_running(999999999)
        assert result is False


class TestCollectArtifacts:
    """Tests for artifact collection functions."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stories_dir = Path(tmpdir) / "data" / "stories"
            research_dir = Path(tmpdir) / "data" / "research"
            stories_dir.mkdir(parents=True)
            research_dir.mkdir(parents=True)
            yield {"root": Path(tmpdir), "stories": stories_dir, "research": research_dir}

    def test_collect_story_artifacts(self, temp_dirs):
        """Should collect story artifacts created after job start."""
        from src.infra.job_monitor import collect_story_artifacts
        from src.infra.job_manager import Job

        # Create a story file
        story_file = temp_dirs["stories"] / "story_001.json"
        story_file.write_text('{"title": "Test Story"}')

        job = Job(
            job_id="test-123",
            type="story_generation",
            status="running",
            started_at=(datetime.now() - timedelta(hours=1)).isoformat()
        )

        with patch("job_monitor.STORY_OUTPUT_DIR", temp_dirs["stories"]):
            artifacts = collect_story_artifacts(job)

        assert len(artifacts) == 1
        assert "story_001.json" in artifacts[0]

    def test_collect_research_artifacts(self, temp_dirs):
        """Should collect research artifacts created after job start."""
        from src.infra.job_monitor import collect_research_artifacts
        from src.infra.job_manager import Job

        # Create a research file
        research_file = temp_dirs["research"] / "RC-001.json"
        research_file.write_text('{"card_id": "RC-001"}')

        job = Job(
            job_id="test-456",
            type="research",
            status="running",
            started_at=(datetime.now() - timedelta(hours=1)).isoformat()
        )

        with patch("job_monitor.RESEARCH_OUTPUT_DIR", temp_dirs["research"]):
            artifacts = collect_research_artifacts(job)

        assert len(artifacts) == 1
        assert "RC-001.json" in artifacts[0]

    def test_no_artifacts_before_start(self, temp_dirs):
        """Should not collect artifacts created before job start."""
        from src.infra.job_monitor import collect_story_artifacts
        from src.infra.job_manager import Job

        # Create a story file
        story_file = temp_dirs["stories"] / "old_story.json"
        story_file.write_text('{"title": "Old Story"}')

        # Set file modification time to 2 hours ago
        old_time = (datetime.now() - timedelta(hours=2)).timestamp()
        os.utime(story_file, (old_time, old_time))

        job = Job(
            job_id="test-789",
            type="story_generation",
            status="running",
            started_at=datetime.now().isoformat()  # Job started now
        )

        with patch("job_monitor.STORY_OUTPUT_DIR", temp_dirs["stories"]):
            artifacts = collect_story_artifacts(job)

        assert len(artifacts) == 0

    def test_collect_artifacts_no_started_at(self):
        """Should return empty list if job has no started_at."""
        from src.infra.job_monitor import collect_story_artifacts
        from src.infra.job_manager import Job

        job = Job(
            job_id="test-no-start",
            type="story_generation",
            status="queued",
            started_at=None
        )

        artifacts = collect_story_artifacts(job)
        assert artifacts == []


class TestCheckJobLogForErrors:
    """Tests for log error checking."""

    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_detect_traceback_error(self, temp_log_dir):
        """Should detect Python traceback in log."""
        from src.infra.job_monitor import check_job_log_for_errors
        from src.infra.job_manager import Job

        log_file = temp_log_dir / "test.log"
        log_file.write_text("""
Starting process...
Traceback (most recent call last):
  File "main.py", line 10
    raise ValueError("Test error")
ValueError: Test error
""")

        job = Job(
            job_id="test-log",
            type="story_generation",
            status="running",
            log_path=str(log_file)
        )

        error = check_job_log_for_errors(job)
        assert error is not None
        assert "Traceback" in error

    def test_no_error_in_clean_log(self, temp_log_dir):
        """Should return None for clean log."""
        from src.infra.job_monitor import check_job_log_for_errors
        from src.infra.job_manager import Job

        log_file = temp_log_dir / "clean.log"
        log_file.write_text("""
Starting process...
Processing story 1...
Processing story 2...
Done!
""")

        job = Job(
            job_id="test-clean",
            type="story_generation",
            status="running",
            log_path=str(log_file)
        )

        error = check_job_log_for_errors(job)
        assert error is None

    def test_no_log_path(self):
        """Should return None if no log path."""
        from src.infra.job_monitor import check_job_log_for_errors
        from src.infra.job_manager import Job

        job = Job(
            job_id="no-log",
            type="story_generation",
            status="running",
            log_path=None
        )

        error = check_job_log_for_errors(job)
        assert error is None


class TestMonitorJob:
    """Tests for monitor_job function."""

    @pytest.fixture
    def temp_jobs_dir(self):
        """Create temporary jobs directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jobs_path = Path(tmpdir) / "jobs"
            jobs_path.mkdir()
            yield jobs_path

    def test_monitor_nonexistent_job(self, temp_jobs_dir):
        """Should return error for nonexistent job."""
        from src.infra.job_monitor import monitor_job

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            with patch("job_monitor.load_job", return_value=None):
                result = monitor_job("nonexistent")

        assert "error" in result
        assert "not found" in result["error"]

    def test_monitor_running_job(self, temp_jobs_dir):
        """Should return running status for active job."""
        from src.infra.job_monitor import monitor_job
        from src.infra.job_manager import Job

        job = Job(
            job_id="running-job",
            type="story_generation",
            status="running",
            pid=os.getpid()  # Current process
        )

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            with patch("job_monitor.load_job", return_value=job):
                result = monitor_job("running-job")

        assert result["status"] == "running"
        assert result["pid"] == os.getpid()

    def test_monitor_completed_job_with_artifacts(self, temp_jobs_dir):
        """Should detect completed job and collect artifacts."""
        from src.infra.job_monitor import monitor_job
        from src.infra.job_manager import Job

        job = Job(
            job_id="completed-job",
            type="story_generation",
            status="running",
            pid=999999999,  # Non-existent PID
            started_at=datetime.now().isoformat()
        )

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            with patch("job_monitor.load_job", return_value=job):
                with patch("job_monitor.collect_artifacts", return_value=["/path/to/story.json"]):
                    with patch("job_monitor.check_job_log_for_errors", return_value=None):
                        with patch("job_monitor.update_job_status") as mock_update:
                            result = monitor_job("completed-job")

        assert result["status"] == "succeeded"
        mock_update.assert_called()


class TestCancelJob:
    """Tests for cancel_job function."""

    @pytest.fixture
    def temp_jobs_dir(self):
        """Create temporary jobs directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jobs_path = Path(tmpdir) / "jobs"
            jobs_path.mkdir()
            yield jobs_path

    def test_cancel_nonexistent_job(self, temp_jobs_dir):
        """Should return error for nonexistent job."""
        from src.infra.job_monitor import cancel_job

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            with patch("job_monitor.load_job", return_value=None):
                result = cancel_job("nonexistent")

        assert result["success"] is False
        assert "not found" in result["error"]

    def test_cancel_non_running_job(self, temp_jobs_dir):
        """Should return error for non-running job."""
        from src.infra.job_monitor import cancel_job
        from src.infra.job_manager import Job

        job = Job(
            job_id="queued-job",
            type="story_generation",
            status="queued",
            pid=None
        )

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            with patch("job_monitor.load_job", return_value=job):
                result = cancel_job("queued-job")

        assert result["success"] is False
        assert "not running" in result["error"]

    def test_cancel_job_process_already_exited(self, temp_jobs_dir):
        """Should handle already exited process."""
        from src.infra.job_monitor import cancel_job
        from src.infra.job_manager import Job

        job = Job(
            job_id="exited-job",
            type="story_generation",
            status="running",
            pid=999999999  # Non-existent PID
        )

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            with patch("job_monitor.load_job", return_value=job):
                with patch("job_monitor.update_job_status"):
                    result = cancel_job("exited-job")

        assert result["success"] is True
        assert "already exited" in result["message"]


class TestMonitorAllRunningJobs:
    """Tests for monitor_all_running_jobs function."""

    def test_monitor_empty_list(self):
        """Should handle no running jobs."""
        from src.infra.job_monitor import monitor_all_running_jobs

        with patch("job_monitor.get_running_jobs", return_value=[]):
            results = monitor_all_running_jobs()

        assert results == []

    def test_monitor_multiple_jobs(self):
        """Should monitor all running jobs."""
        from src.infra.job_monitor import monitor_all_running_jobs
        from src.infra.job_manager import Job

        jobs = [
            Job(job_id="job-1", type="story_generation", status="running", pid=os.getpid()),
            Job(job_id="job-2", type="research", status="running", pid=os.getpid()),
        ]

        with patch("job_monitor.get_running_jobs", return_value=jobs):
            with patch("job_monitor.load_job", side_effect=lambda jid: next((j for j in jobs if j.job_id == jid), None)):
                results = monitor_all_running_jobs()

        assert len(results) == 2


class TestMonitorEndpoints:
    """Tests for monitor API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client for API."""
        from src.api.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)

    @pytest.fixture
    def temp_jobs_dir(self):
        """Create temporary jobs directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jobs_path = Path(tmpdir) / "jobs"
            jobs_path.mkdir()
            yield jobs_path

    def test_cancel_endpoint(self, client, temp_jobs_dir):
        """Should call cancel via API."""
        from src.infra.job_manager import Job

        job = Job(
            job_id="cancel-test",
            type="story_generation",
            status="running",
            pid=999999999
        )

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            with patch("job_monitor.load_job", return_value=job):
                with patch("job_monitor.update_job_status"):
                    response = client.post("/jobs/cancel-test/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "cancel-test"
        assert data["success"] is True

    def test_monitor_all_endpoint(self, client, temp_jobs_dir):
        """Should monitor all jobs via API."""
        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            with patch("job_monitor.get_running_jobs", return_value=[]):
                response = client.post("/jobs/monitor")

        assert response.status_code == 200
        data = response.json()
        assert data["monitored_count"] == 0
        assert data["results"] == []

    def test_monitor_single_endpoint(self, client, temp_jobs_dir):
        """Should monitor single job via API."""
        from src.infra.job_manager import Job

        job = Job(
            job_id="single-test",
            type="story_generation",
            status="running",
            pid=os.getpid()
        )

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            with patch("job_monitor.load_job", return_value=job):
                response = client.post("/jobs/single-test/monitor")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "single-test"
        assert data["status"] == "running"
