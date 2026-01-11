"""
Tests for jobs router.

Phase B+: Trigger API endpoint tests.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client for API."""
    from research_api.main import app
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

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            with patch("research_api.routers.jobs.LOGS_DIR", logs_dir):
                with patch("research_api.routers.jobs.subprocess.Popen") as mock_popen:
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

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            with patch("research_api.routers.jobs.LOGS_DIR", logs_dir):
                with patch("research_api.routers.jobs.subprocess.Popen") as mock_popen:
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

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            with patch("research_api.routers.jobs.LOGS_DIR", logs_dir):
                with patch("research_api.routers.jobs.subprocess.Popen") as mock_popen:
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
    """Tests for GET /jobs/{job_id} endpoint."""

    def test_get_job_status(self, client, temp_jobs_dir):
        """Should return job status."""
        from job_manager import create_job, update_job_status

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            # Create a job directly
            job = create_job("story_generation", {"max_stories": 1})
            update_job_status(job.job_id, "running", pid=11111)

            response = client.get(f"/jobs/{job.job_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == job.job_id
            assert data["type"] == "story_generation"
            assert data["status"] == "running"
            assert data["pid"] == 11111

    def test_get_nonexistent_job(self, client, temp_jobs_dir):
        """Should return 404 for nonexistent job."""
        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            response = client.get("/jobs/nonexistent-job-id")

            assert response.status_code == 404


class TestJobListEndpoint:
    """Tests for GET /jobs endpoint."""

    def test_list_jobs_empty(self, client, temp_jobs_dir):
        """Should return empty list when no jobs."""
        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            response = client.get("/jobs")

            assert response.status_code == 200
            data = response.json()
            assert data["jobs"] == []
            assert data["total"] == 0

    def test_list_jobs_with_filter(self, client, temp_jobs_dir):
        """Should filter jobs by status and type."""
        from job_manager import create_job, update_job_status

        with patch("job_manager.JOBS_DIR", temp_jobs_dir):
            # Create jobs
            job1 = create_job("story_generation", {})
            job2 = create_job("research", {})
            update_job_status(job1.job_id, "running")

            # Filter by status
            response = client.get("/jobs?status=running")
            data = response.json()
            assert data["total"] == 1

            # Filter by type
            response = client.get("/jobs?type=research")
            data = response.json()
            assert data["total"] == 1


class TestBuildCommands:
    """Tests for command building functions."""

    def test_build_story_command(self):
        """Should build correct story generation command."""
        from research_api.routers.jobs import build_story_command, PROJECT_ROOT
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
        from research_api.routers.jobs import build_research_command
        import sys

        params = {
            "topic": "Korean horror",
            "tags": ["urban", "psychological"],
            "model": "qwen3:30b",
            "timeout": 120
        }

        cmd = build_research_command(params)

        assert "-m" in cmd
        assert "research_executor" in cmd
        assert "--topic" in cmd
        assert "Korean horror" in cmd
        assert "--tag" in cmd
        assert "--model" in cmd

    def test_build_story_command_minimal(self):
        """Should build minimal command with defaults."""
        from research_api.routers.jobs import build_story_command

        params = {}
        cmd = build_story_command(params)

        # Should only have python and main.py
        assert len(cmd) == 2

    def test_build_research_command_minimal(self):
        """Should build minimal research command."""
        from research_api.routers.jobs import build_research_command

        params = {"topic": "test", "tags": []}
        cmd = build_research_command(params)

        assert "--topic" in cmd
        assert "--tag" not in cmd
