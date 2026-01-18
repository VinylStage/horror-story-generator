"""
Tests for jobs router.

Phase B+: Trigger API endpoint tests.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client for API."""
    from src.api.main import app
    return TestClient(app)


@pytest.fixture
def temp_jobs_dir():
    """Create temporary jobs directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        jobs_path = Path(tmpdir) / "jobs"
        jobs_path.mkdir()
        yield jobs_path


class TestStoryTriggerEndpoint:
    """Tests for POST /jobs/story/trigger endpoint."""

    def test_trigger_story_generation(self, client, temp_jobs_dir):
        """Should trigger story generation and return job_id."""
        logs_dir = temp_jobs_dir.parent / "logs"
        logs_dir.mkdir(exist_ok=True)

        with patch("src.infra.job_manager.JOBS_DIR", temp_jobs_dir):
            with patch("src.api.routers.jobs.LOGS_DIR", logs_dir):
                with patch("src.api.routers.jobs.subprocess.Popen") as mock_popen:
                    mock_process = MagicMock()
                    mock_process.pid = 12345
                    mock_popen.return_value = mock_process

                    response = client.post(
                        "/jobs/story/trigger",
                        json={"max_stories": 3, "enable_dedup": True}
                    )

                    assert response.status_code == 202
                    data = response.json()
                    assert "job_id" in data
                    assert data["type"] == "story_generation"
                    assert data["status"] == "running"

    def test_trigger_with_all_params(self, client, temp_jobs_dir):
        """Should accept all story generation parameters."""
        logs_dir = temp_jobs_dir.parent / "logs"
        logs_dir.mkdir(exist_ok=True)

        with patch("src.infra.job_manager.JOBS_DIR", temp_jobs_dir):
            with patch("src.api.routers.jobs.LOGS_DIR", logs_dir):
                with patch("src.api.routers.jobs.subprocess.Popen") as mock_popen:
                    mock_process = MagicMock()
                    mock_process.pid = 99999
                    mock_popen.return_value = mock_process

                    response = client.post(
                        "/jobs/story/trigger",
                        json={
                            "max_stories": 5,
                            "duration_seconds": 300,
                            "interval_seconds": 10,
                            "enable_dedup": True,
                            "db_path": "/tmp/test.db",
                            "load_history": True
                        }
                    )

                    assert response.status_code == 202

    def test_trigger_with_invalid_params(self, client):
        """Should reject invalid parameters."""
        response = client.post(
            "/jobs/story/trigger",
            json={"max_stories": -1}  # Invalid: must be >= 1
        )

        assert response.status_code == 422


class TestResearchTriggerEndpoint:
    """Tests for POST /jobs/research/trigger endpoint."""

    def test_trigger_research_generation(self, client, temp_jobs_dir):
        """Should trigger research generation and return job_id."""
        logs_dir = temp_jobs_dir.parent / "logs"
        logs_dir.mkdir(exist_ok=True)

        with patch("src.infra.job_manager.JOBS_DIR", temp_jobs_dir):
            with patch("src.api.routers.jobs.LOGS_DIR", logs_dir):
                with patch("src.api.routers.jobs.subprocess.Popen") as mock_popen:
                    mock_process = MagicMock()
                    mock_process.pid = 54321
                    mock_popen.return_value = mock_process

                    response = client.post(
                        "/jobs/research/trigger",
                        json={
                            "topic": "Korean apartment horror",
                            "tags": ["urban", "isolation"]
                        }
                    )

                    assert response.status_code == 202
                    data = response.json()
                    assert "job_id" in data
                    assert data["type"] == "research"
                    assert data["status"] == "running"

    def test_trigger_research_requires_topic(self, client):
        """Should require topic parameter."""
        response = client.post(
            "/jobs/research/trigger",
            json={"tags": ["test"]}  # Missing required topic
        )

        assert response.status_code == 422


class TestJobStatusEndpoint:
    """Tests for GET /jobs/{job_id} endpoint (Scheduler-based, Phase 3)."""

    def test_get_job_status(self, client):
        """Should return job status from scheduler."""
        from unittest.mock import MagicMock
        from src.scheduler.entities import Job, JobStatus

        mock_job = MagicMock(spec=Job)
        mock_job.job_id = "test-job-123"
        mock_job.job_type = "story"
        mock_job.status = JobStatus.QUEUED
        mock_job.params = {"max_stories": 1}
        mock_job.priority = 0
        mock_job.position = 1
        mock_job.template_id = None
        mock_job.group_id = None
        mock_job.retry_of = None
        mock_job.created_at = "2026-01-18T10:00:00"
        mock_job.queued_at = "2026-01-18T10:00:00"
        mock_job.started_at = None
        mock_job.finished_at = None

        with patch("src.api.routers.jobs.get_scheduler_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_job.return_value = mock_job
            mock_get_service.return_value = mock_service

            response = client.get("/jobs/test-job-123")

            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == "test-job-123"
            assert data["job_type"] == "story"
            assert data["status"] == "QUEUED"

    def test_get_nonexistent_job(self, client):
        """Should return 404 for nonexistent job."""
        with patch("src.api.routers.jobs.get_scheduler_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_job.return_value = None
            mock_get_service.return_value = mock_service

            response = client.get("/jobs/nonexistent-job-id")

            assert response.status_code == 404


class TestJobListEndpoint:
    """Tests for GET /jobs endpoint (Scheduler-based, Phase 3)."""

    def test_list_jobs_empty(self, client):
        """Should return empty list when no jobs."""
        with patch("src.api.routers.jobs.get_scheduler_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.list_all_jobs.return_value = []
            mock_service.get_queue_stats.return_value = {
                "queued_count": 0,
                "running_count": 0,
            }
            mock_get_service.return_value = mock_service

            response = client.get("/jobs")

            assert response.status_code == 200
            data = response.json()
            assert data["jobs"] == []
            assert data["total"] == 0

    def test_list_jobs_with_jobs(self, client):
        """Should return jobs from scheduler."""
        from unittest.mock import MagicMock
        from src.scheduler.entities import Job, JobStatus

        mock_job1 = MagicMock(spec=Job)
        mock_job1.job_id = "job-1"
        mock_job1.job_type = "story"
        mock_job1.status = JobStatus.RUNNING
        mock_job1.params = {}
        mock_job1.priority = 0
        mock_job1.position = 0
        mock_job1.template_id = None
        mock_job1.group_id = None
        mock_job1.retry_of = None
        mock_job1.created_at = "2026-01-18T10:00:00"
        mock_job1.queued_at = "2026-01-18T10:00:00"
        mock_job1.started_at = "2026-01-18T10:01:00"
        mock_job1.finished_at = None

        mock_job2 = MagicMock(spec=Job)
        mock_job2.job_id = "job-2"
        mock_job2.job_type = "research"
        mock_job2.status = JobStatus.QUEUED
        mock_job2.params = {"topic": "test"}
        mock_job2.priority = 5
        mock_job2.position = 1
        mock_job2.template_id = None
        mock_job2.group_id = None
        mock_job2.retry_of = None
        mock_job2.created_at = "2026-01-18T10:00:00"
        mock_job2.queued_at = "2026-01-18T10:00:00"
        mock_job2.started_at = None
        mock_job2.finished_at = None

        with patch("src.api.routers.jobs.get_scheduler_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.list_all_jobs.return_value = [mock_job1, mock_job2]
            mock_service.get_queue_stats.return_value = {
                "queued_count": 1,
                "running_count": 1,
            }
            mock_get_service.return_value = mock_service

            response = client.get("/jobs")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert data["queued_count"] == 1
            assert data["running_count"] == 1


class TestBuildCommands:
    """Tests for command building functions."""

    def test_build_story_command(self):
        """Should build correct story generation command."""
        from src.api.routers.jobs import build_story_command, PROJECT_ROOT
        import sys

        params = {
            "max_stories": 5,
            "duration_seconds": 300,
            "interval_seconds": 10,
            "enable_dedup": True,
            "db_path": "/tmp/test.db",
            "load_history": True
        }

        cmd = build_story_command(params)

        assert sys.executable in cmd[0]
        assert "--max-stories" in cmd
        assert "5" in cmd
        assert "--duration-seconds" in cmd
        assert "--enable-dedup" in cmd
        assert "--load-history" in cmd

    def test_build_research_command(self):
        """Should build correct research generation command."""
        from src.api.routers.jobs import build_research_command
        import sys

        params = {
            "topic": "Korean horror",
            "tags": ["urban", "psychological"],
            "model": "qwen3:30b",
            "timeout": 120
        }

        cmd = build_research_command(params)

        assert "-m" in cmd
        assert "src.research.executor" in cmd
        assert "run" in cmd
        assert "Korean horror" in cmd
        assert "--tags" in cmd
        assert "urban" in cmd
        assert "psychological" in cmd
        assert "--model" in cmd

    def test_build_story_command_minimal(self):
        """Should build minimal command with defaults."""
        from src.api.routers.jobs import build_story_command

        params = {}
        cmd = build_story_command(params)

        # Should only have python and main.py
        assert len(cmd) == 2

    def test_build_research_command_minimal(self):
        """Should build minimal research command."""
        from src.api.routers.jobs import build_research_command

        params = {"topic": "test", "tags": []}
        cmd = build_research_command(params)

        assert "run" in cmd
        assert "test" in cmd
        assert "--tags" not in cmd


class TestDedupCheckEndpoint:
    """Tests for POST /jobs/{job_id}/dedup_check endpoint."""

    @pytest.fixture
    def temp_jobs_dir(self):
        """Create temporary jobs directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jobs_path = Path(tmpdir) / "jobs"
            jobs_path.mkdir()
            yield jobs_path

    @pytest.fixture
    def client(self):
        """Create test client for API."""
        from src.api.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_dedup_check_nonexistent_job(self, client, temp_jobs_dir):
        """Should return 404 for nonexistent job."""
        with patch("src.infra.job_manager.JOBS_DIR", temp_jobs_dir):
            response = client.post("/jobs/nonexistent/dedup_check")

        assert response.status_code == 404

    def test_dedup_check_story_job_rejected(self, client, temp_jobs_dir):
        """Should reject story job type."""
        from src.infra.job_manager import Job

        job = Job(
            job_id="story-job",
            type="story_generation",
            status="succeeded",
            artifacts=["/path/to/story.json"]
        )

        with patch("src.infra.job_manager.JOBS_DIR", temp_jobs_dir):
            with patch("src.api.routers.jobs.load_job", return_value=job):
                response = client.post("/jobs/story-job/dedup_check")

        assert response.status_code == 200
        data = response.json()
        assert data["has_artifact"] is False
        assert "only available for research" in data["message"]

    def test_dedup_check_no_artifacts(self, client, temp_jobs_dir):
        """Should handle job with no artifacts."""
        from src.infra.job_manager import Job

        job = Job(
            job_id="research-empty",
            type="research",
            status="running",
            artifacts=[]
        )

        with patch("src.infra.job_manager.JOBS_DIR", temp_jobs_dir):
            with patch("src.api.routers.jobs.load_job", return_value=job):
                response = client.post("/jobs/research-empty/dedup_check")

        assert response.status_code == 200
        data = response.json()
        assert data["has_artifact"] is False
        assert "no artifacts" in data["message"]

    def test_dedup_check_with_artifact(self, client, temp_jobs_dir):
        """Should evaluate dedup for research job with artifact."""
        from src.infra.job_manager import Job

        # Create a temporary research card file
        research_dir = temp_jobs_dir.parent / "research"
        research_dir.mkdir()
        card_file = research_dir / "RC-test.json"
        card_file.write_text(json.dumps({
            "card_id": "RC-test",
            "output": {
                "title": "Test Research Card",
                "canonical_affinity": {
                    "setting": ["urban"],
                    "primary_fear": ["isolation"],
                    "antagonist": ["system"],
                    "mechanism": ["surveillance"]
                }
            }
        }))

        job = Job(
            job_id="research-with-card",
            type="research",
            status="succeeded",
            artifacts=[str(card_file)]
        )

        with patch("src.infra.job_manager.JOBS_DIR", temp_jobs_dir):
            with patch("src.api.routers.jobs.load_job", return_value=job):
                with patch("src.api.services.dedup_service.evaluate_dedup") as mock_dedup:
                    mock_dedup.return_value = {
                        "signal": "LOW",
                        "similarity_score": 0.1,
                        "message": None
                    }

                    response = client.post("/jobs/research-with-card/dedup_check")

        assert response.status_code == 200
        data = response.json()
        assert data["has_artifact"] is True
        assert data["signal"] == "LOW"
        assert data["similarity_score"] == 0.1


# =============================================================================
# Batch Job Tests (v1.4.0)
# =============================================================================


class TestBatchTriggerEndpoint:
    """Tests for POST /jobs/batch/trigger endpoint."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary jobs and batches directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jobs_path = Path(tmpdir) / "jobs"
            batches_path = Path(tmpdir) / "batches"
            jobs_path.mkdir()
            batches_path.mkdir()
            yield jobs_path, batches_path

    @pytest.fixture
    def client(self):
        """Create test client for API."""
        from src.api.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_batch_trigger_research_jobs(self, client, temp_dirs):
        """Should trigger multiple research jobs as a batch."""
        jobs_path, batches_path = temp_dirs
        logs_dir = jobs_path.parent / "logs"
        logs_dir.mkdir(exist_ok=True)

        with patch("src.infra.job_manager.JOBS_DIR", jobs_path):
            with patch("src.infra.job_manager.BATCHES_DIR", batches_path):
                with patch("src.api.routers.jobs.LOGS_DIR", logs_dir):
                    with patch("src.api.routers.jobs.subprocess.Popen") as mock_popen:
                        mock_process = MagicMock()
                        mock_process.pid = 12345
                        mock_popen.return_value = mock_process

                        response = client.post(
                            "/jobs/batch/trigger",
                            json={
                                "jobs": [
                                    {"type": "research", "topic": "Topic 1"},
                                    {"type": "research", "topic": "Topic 2"},
                                ]
                            }
                        )

                        assert response.status_code == 202
                        data = response.json()
                        assert "batch_id" in data
                        assert data["batch_id"].startswith("batch-")
                        assert len(data["job_ids"]) == 2
                        assert data["job_count"] == 2

    def test_batch_trigger_mixed_jobs(self, client, temp_dirs):
        """Should trigger mixed research and story jobs."""
        jobs_path, batches_path = temp_dirs
        logs_dir = jobs_path.parent / "logs"
        logs_dir.mkdir(exist_ok=True)

        with patch("src.infra.job_manager.JOBS_DIR", jobs_path):
            with patch("src.infra.job_manager.BATCHES_DIR", batches_path):
                with patch("src.api.routers.jobs.LOGS_DIR", logs_dir):
                    with patch("src.api.routers.jobs.subprocess.Popen") as mock_popen:
                        mock_process = MagicMock()
                        mock_process.pid = 99999
                        mock_popen.return_value = mock_process

                        response = client.post(
                            "/jobs/batch/trigger",
                            json={
                                "jobs": [
                                    {"type": "research", "topic": "Horror research"},
                                    {"type": "story", "max_stories": 2},
                                ]
                            }
                        )

                        assert response.status_code == 202
                        data = response.json()
                        assert len(data["job_ids"]) == 2

    def test_batch_trigger_requires_topic_for_research(self, client, temp_dirs):
        """Should reject research job without topic."""
        jobs_path, batches_path = temp_dirs
        logs_dir = jobs_path.parent / "logs"
        logs_dir.mkdir(exist_ok=True)

        with patch("src.infra.job_manager.JOBS_DIR", jobs_path):
            with patch("src.infra.job_manager.BATCHES_DIR", batches_path):
                with patch("src.api.routers.jobs.LOGS_DIR", logs_dir):
                    with patch("src.api.routers.jobs.subprocess.Popen") as mock_popen:
                        mock_process = MagicMock()
                        mock_process.pid = 11111
                        mock_popen.return_value = mock_process

                        response = client.post(
                            "/jobs/batch/trigger",
                            json={
                                "jobs": [
                                    {"type": "research"},  # Missing topic
                                    {"type": "story", "max_stories": 1},
                                ]
                            }
                        )

                        # Should still succeed with 1 job
                        assert response.status_code == 202
                        data = response.json()
                        assert len(data["job_ids"]) == 1
                        assert "requires 'topic'" in data["message"]

    def test_batch_trigger_empty_jobs_fails(self, client):
        """Should reject empty jobs array."""
        response = client.post(
            "/jobs/batch/trigger",
            json={"jobs": []}
        )

        assert response.status_code == 422


class TestBatchStatusEndpoint:
    """Tests for GET /jobs/batch/{batch_id} endpoint."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary jobs and batches directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jobs_path = Path(tmpdir) / "jobs"
            batches_path = Path(tmpdir) / "batches"
            jobs_path.mkdir()
            batches_path.mkdir()
            yield jobs_path, batches_path

    @pytest.fixture
    def client(self):
        """Create test client for API."""
        from src.api.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_get_batch_status(self, client, temp_dirs):
        """Should return batch status with job details."""
        jobs_path, batches_path = temp_dirs

        from src.infra.job_manager import Job, Batch

        # Create mock jobs
        job1 = Job(job_id="job-1", type="research", status="succeeded")
        job2 = Job(job_id="job-2", type="research", status="running")

        # Create mock batch
        batch = Batch(
            batch_id="batch-test123",
            job_ids=["job-1", "job-2"],
            status="running",
        )

        with patch("src.infra.job_manager.JOBS_DIR", jobs_path):
            with patch("src.infra.job_manager.BATCHES_DIR", batches_path):
                with patch("src.infra.job_manager.load_batch", return_value=batch):
                    with patch("src.infra.job_manager.load_job") as mock_load_job:
                        def load_job_side_effect(job_id):
                            if job_id == "job-1":
                                return job1
                            elif job_id == "job-2":
                                return job2
                            return None

                        mock_load_job.side_effect = load_job_side_effect

                        response = client.get("/jobs/batch/batch-test123")

                        assert response.status_code == 200
                        data = response.json()
                        assert data["batch_id"] == "batch-test123"
                        assert data["status"] == "running"
                        assert data["total_jobs"] == 2
                        assert data["succeeded_jobs"] == 1
                        assert data["running_jobs"] == 1
                        assert len(data["jobs"]) == 2

    def test_get_nonexistent_batch(self, client, temp_dirs):
        """Should return 404 for nonexistent batch."""
        jobs_path, batches_path = temp_dirs

        with patch("src.infra.job_manager.JOBS_DIR", jobs_path):
            with patch("src.infra.job_manager.BATCHES_DIR", batches_path):
                response = client.get("/jobs/batch/nonexistent-batch")

                assert response.status_code == 404
