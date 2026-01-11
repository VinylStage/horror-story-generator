"""
Tests for job_manager module.

Phase B+: File-based job storage tests.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest


class TestJobDataclass:
    """Tests for Job dataclass."""

    def test_create_job(self):
        """Should create job with correct fields."""
        from src.infra.job_manager import Job

        job = Job(
            job_id="test-123",
            type="story_generation",
            status="queued",
            params={"max_stories": 5}
        )

        assert job.job_id == "test-123"
        assert job.type == "story_generation"
        assert job.status == "queued"
        assert job.params == {"max_stories": 5}
        assert job.pid is None
        assert job.artifacts == []
        assert job.created_at is not None

    def test_to_dict(self):
        """Should convert job to dictionary."""
        from src.infra.job_manager import Job

        job = Job(
            job_id="test-123",
            type="research",
            status="running",
            pid=12345
        )

        d = job.to_dict()

        assert d["job_id"] == "test-123"
        assert d["type"] == "research"
        assert d["status"] == "running"
        assert d["pid"] == 12345

    def test_from_dict(self):
        """Should create job from dictionary."""
        from src.infra.job_manager import Job

        data = {
            "job_id": "test-456",
            "type": "story_generation",
            "status": "succeeded",
            "params": {"enable_dedup": True},
            "pid": 9999,
            "log_path": "/tmp/log.txt",
            "artifacts": ["/tmp/story.json"],
            "created_at": "2026-01-11T10:00:00",
            "started_at": "2026-01-11T10:00:01",
            "finished_at": "2026-01-11T10:05:00",
            "exit_code": 0,
            "error": None
        }

        job = Job.from_dict(data)

        assert job.job_id == "test-456"
        assert job.status == "succeeded"
        assert job.exit_code == 0
        assert job.artifacts == ["/tmp/story.json"]


class TestJobOperations:
    """Tests for job file operations."""

    @pytest.fixture
    def temp_jobs_dir(self):
        """Create temporary jobs directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jobs_path = Path(tmpdir) / "jobs"
            jobs_path.mkdir()
            yield jobs_path

    def test_create_job(self, temp_jobs_dir):
        """Should create and save job."""
        from src.infra.job_manager import create_job, JOBS_DIR

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            job = create_job(
                job_type="story_generation",
                params={"max_stories": 3}
            )

            assert job.job_id is not None
            assert job.type == "story_generation"
            assert job.status == "queued"

            # Check file exists
            job_file = temp_jobs_dir / f"{job.job_id}.json"
            assert job_file.exists()

    def test_save_job(self, temp_jobs_dir):
        """Should save job to disk."""
        from src.infra.job_manager import Job, save_job

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            job = Job(
                job_id="save-test",
                type="research",
                status="queued"
            )

            result = save_job(job)

            assert result is True
            assert (temp_jobs_dir / "save-test.json").exists()

    def test_load_job(self, temp_jobs_dir):
        """Should load job from disk."""
        from src.infra.job_manager import Job, save_job, load_job

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            original = Job(
                job_id="load-test",
                type="story_generation",
                status="running",
                pid=5678
            )
            save_job(original)

            loaded = load_job("load-test")

            assert loaded is not None
            assert loaded.job_id == "load-test"
            assert loaded.pid == 5678

    def test_load_nonexistent_job(self, temp_jobs_dir):
        """Should return None for nonexistent job."""
        from src.infra.job_manager import load_job

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            result = load_job("nonexistent")

            assert result is None

    def test_update_job_status_to_running(self, temp_jobs_dir):
        """Should update job status to running with started_at."""
        from src.infra.job_manager import create_job, update_job_status, load_job

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            job = create_job("research", {})

            update_job_status(job.job_id, "running", pid=9999)

            updated = load_job(job.job_id)
            assert updated.status == "running"
            assert updated.pid == 9999
            assert updated.started_at is not None

    def test_update_job_status_to_succeeded(self, temp_jobs_dir):
        """Should update job status to succeeded with finished_at."""
        from src.infra.job_manager import create_job, update_job_status, load_job

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            job = create_job("story_generation", {})
            update_job_status(job.job_id, "running", pid=1234)

            update_job_status(
                job.job_id,
                "succeeded",
                exit_code=0,
                artifacts=["/path/to/story.json"]
            )

            updated = load_job(job.job_id)
            assert updated.status == "succeeded"
            assert updated.exit_code == 0
            assert updated.finished_at is not None
            assert "/path/to/story.json" in updated.artifacts

    def test_update_job_status_to_failed(self, temp_jobs_dir):
        """Should update job status to failed with error."""
        from src.infra.job_manager import create_job, update_job_status, load_job

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            job = create_job("research", {})

            update_job_status(
                job.job_id,
                "failed",
                exit_code=1,
                error="Process crashed"
            )

            updated = load_job(job.job_id)
            assert updated.status == "failed"
            assert updated.exit_code == 1
            assert updated.error == "Process crashed"

    def test_update_nonexistent_job(self, temp_jobs_dir):
        """Should return False for nonexistent job."""
        from src.infra.job_manager import update_job_status

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            result = update_job_status("nonexistent", "running")

            assert result is False

    def test_list_jobs(self, temp_jobs_dir):
        """Should list all jobs."""
        from src.infra.job_manager import create_job, list_jobs

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            create_job("story_generation", {"id": 1})
            create_job("research", {"id": 2})
            create_job("story_generation", {"id": 3})

            jobs = list_jobs()

            assert len(jobs) == 3

    def test_list_jobs_with_status_filter(self, temp_jobs_dir):
        """Should filter jobs by status."""
        from src.infra.job_manager import create_job, update_job_status, list_jobs

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            job1 = create_job("story_generation", {})
            job2 = create_job("research", {})
            job3 = create_job("story_generation", {})

            update_job_status(job1.job_id, "running")
            update_job_status(job2.job_id, "succeeded", exit_code=0)

            running_jobs = list_jobs(status="running")
            queued_jobs = list_jobs(status="queued")

            assert len(running_jobs) == 1
            assert len(queued_jobs) == 1

    def test_list_jobs_with_type_filter(self, temp_jobs_dir):
        """Should filter jobs by type."""
        from src.infra.job_manager import create_job, list_jobs

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            create_job("story_generation", {})
            create_job("research", {})
            create_job("story_generation", {})

            story_jobs = list_jobs(job_type="story_generation")
            research_jobs = list_jobs(job_type="research")

            assert len(story_jobs) == 2
            assert len(research_jobs) == 1

    def test_list_jobs_with_limit(self, temp_jobs_dir):
        """Should respect limit parameter."""
        from src.infra.job_manager import create_job, list_jobs

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            for i in range(10):
                create_job("story_generation", {"id": i})

            jobs = list_jobs(limit=5)

            assert len(jobs) == 5

    def test_delete_job(self, temp_jobs_dir):
        """Should delete job from disk."""
        from src.infra.job_manager import create_job, delete_job, load_job

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            job = create_job("research", {})
            job_id = job.job_id

            result = delete_job(job_id)

            assert result is True
            assert load_job(job_id) is None

    def test_delete_nonexistent_job(self, temp_jobs_dir):
        """Should return False for nonexistent job."""
        from src.infra.job_manager import delete_job

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            result = delete_job("nonexistent")

            assert result is False

    def test_get_running_jobs(self, temp_jobs_dir):
        """Should get all running jobs."""
        from src.infra.job_manager import create_job, update_job_status, get_running_jobs

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            job1 = create_job("story_generation", {})
            job2 = create_job("research", {})

            update_job_status(job1.job_id, "running", pid=1111)
            update_job_status(job2.job_id, "running", pid=2222)

            running = get_running_jobs()

            assert len(running) == 2

    def test_get_queued_jobs(self, temp_jobs_dir):
        """Should get all queued jobs."""
        from src.infra.job_manager import create_job, update_job_status, get_queued_jobs

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            job1 = create_job("story_generation", {})
            job2 = create_job("research", {})
            job3 = create_job("story_generation", {})

            update_job_status(job2.job_id, "running")

            queued = get_queued_jobs()

            assert len(queued) == 2


class TestJobManagerErrorHandling:
    """Tests for error handling in job manager."""

    @pytest.fixture
    def temp_jobs_dir(self):
        """Create temporary jobs directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jobs_path = Path(tmpdir) / "jobs"
            jobs_path.mkdir()
            yield jobs_path

    def test_save_job_handles_write_error(self, temp_jobs_dir):
        """Should handle write errors gracefully."""
        from src.infra.job_manager import Job, save_job

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            job = Job(job_id="error-test", type="research", status="queued")

            with patch("builtins.open", side_effect=IOError("Write failed")):
                result = save_job(job)

                assert result is False

    def test_load_job_handles_read_error(self, temp_jobs_dir):
        """Should handle read errors gracefully."""
        from src.infra.job_manager import load_job

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            # Create a corrupted file
            (temp_jobs_dir / "corrupted.json").write_text("not valid json")

            result = load_job("corrupted")

            assert result is None

    def test_list_jobs_handles_corrupted_files(self, temp_jobs_dir):
        """Should skip corrupted files in listing."""
        from src.infra.job_manager import create_job, list_jobs

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            create_job("story_generation", {})

            # Create a corrupted file
            (temp_jobs_dir / "corrupted.json").write_text("invalid")

            jobs = list_jobs()

            assert len(jobs) == 1  # Only valid job counted

    def test_ensure_jobs_dir_creates_directory(self):
        """Should create jobs directory if missing."""
        from src.infra.job_manager import ensure_jobs_dir

        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = Path(tmpdir) / "new_jobs"

            with patch("job_manager.JOBS_DIR", new_dir):
                result = ensure_jobs_dir()

                assert new_dir.exists()
