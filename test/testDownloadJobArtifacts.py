import io
import os
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from unittest import mock

from vine import Gitlab
from vine.downloadJobArtifacts import DownloadJobArtifacts, parse_cli_datetime


class FakeJob:
    def __init__(self, job_id, name, finished_at=None, started_at=None, created_at=None, artifact_bytes=None):
        self.id = job_id
        self.name = name
        self.finished_at = finished_at
        self.started_at = started_at
        self.created_at = created_at
        self.web_url = f"https://gitlab.example/jobs/{job_id}"
        self._artifact_bytes = artifact_bytes

    def artifacts(self):
        return self._artifact_bytes


class FakeJobsManager:
    def __init__(self, jobs):
        self._jobs = {job.id: job for job in jobs}
        self.list_calls = []

    def list(self, all=True, scope=None):
        self.list_calls.append({"all": all, "scope": scope})
        return list(self._jobs.values())

    def get(self, job_id):
        return self._jobs[int(job_id)]


class FakeProject:
    def __init__(self, jobs):
        self.jobs = FakeJobsManager(jobs)


class FakeRepo:
    def __init__(self):
        self.calls = []

    def download_job_artifacts(self, **kwargs):
        self.calls.append(kwargs)
        return [{"download_path": "/tmp/output/file.log"}]


class FakeGitHost:
    def __init__(self, repo):
        self._repo = repo
        self.repo_calls = []

    def repo(self, project_name, repo_name):
        self.repo_calls.append((project_name, repo_name))
        return self._repo


def build_artifact_zip(members):
    artifact_bytes = io.BytesIO()
    with zipfile.ZipFile(artifact_bytes, "w") as archive:
        for name, contents in members.items():
            archive.writestr(name, contents)
    return artifact_bytes.getvalue()


class TestGitlabArtifactDownloads(unittest.TestCase):
    def test_find_failed_jobs_filters_by_time_range_and_name(self):
        jobs = [
            FakeJob(1, "unit", finished_at="2026-07-13T18:00:00Z"),
            FakeJob(2, "lint", finished_at="2026-07-14T08:00:00Z"),
            FakeJob(3, "lint", finished_at="2026-07-15T08:00:00Z"),
        ]
        repo = Gitlab.Repo(FakeProject(jobs), gitlab=None)

        matching = repo.find_failed_jobs(
            datetime(2026, 7, 14, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 7, 14, 23, 59, tzinfo=timezone.utc),
            job_name="lint",
        )

        self.assertEqual([2], [job.id for job in matching])
        self.assertEqual("failed", repo.project.jobs.list_calls[0]["scope"])

    def test_download_job_artifacts_extracts_only_matching_files(self):
        job = FakeJob(
            42,
            "integration test",
            finished_at="2026-07-14T08:00:00Z",
            artifact_bytes=build_artifact_zip(
                {
                    "reports/junit.xml": "<testsuite />",
                    "logs/output.log": "hello",
                    "logs/debug.txt": "skip",
                }
            ),
        )
        repo = Gitlab.Repo(FakeProject([job]), gitlab=None)

        with tempfile.TemporaryDirectory() as tmpdir:
            downloads = repo.download_job_artifacts(
                artifact_filter="*.xml",
                output_dir=tmpdir,
                job_id="42",
            )

            self.assertEqual(1, len(downloads))
            self.assertTrue(downloads[0]["download_path"].endswith("reports/junit.xml"))
            self.assertTrue(os.path.exists(downloads[0]["download_path"]))
            self.assertFalse(
                os.path.exists(os.path.join(tmpdir, "job_42_integration_test", "logs", "output.log"))
            )


class TestDownloadJobArtifactsCommand(unittest.TestCase):
    def test_parse_cli_datetime_expands_date_only_end_of_day(self):
        parsed = parse_cli_datetime("2026-07-14", end_of_day=True)

        self.assertEqual(datetime(2026, 7, 14, 23, 59, 59, 999999, tzinfo=timezone.utc), parsed)

    def test_execute_requires_time_range_when_job_id_not_provided(self):
        command = DownloadJobArtifacts()
        command._workspace_dir = os.getcwd()

        ret = command.execute(
            {
                "--job-id": None,
                "--job-name": None,
                "--start": None,
                "--end": None,
                "--artifact-filter": "*.xml",
                "--output-dir": ".",
                "--user": "alice",
                "--codeReviewsURL": "https://gitlab.example/gitlab",
                "--verifySSL": "True",
                "--project": "grp",
                "--repo": "repo",
                "--ssh_pat_url": "git@example",
                "--ssh_pat_port": "22",
            }
        )

        self.assertFalse(ret)

    def test_execute_forwards_request_to_repo(self):
        command = DownloadJobArtifacts()
        command._workspace_dir = os.getcwd()
        fake_repo = FakeRepo()
        fake_host = FakeGitHost(fake_repo)

        with mock.patch("vine.downloadJobArtifacts.utility.getUserName", return_value="alice"), \
             mock.patch("vine.downloadJobArtifacts.utility.authenticateToGitHost", return_value=fake_host):
            ret = command.execute(
                {
                    "--job-id": "123",
                    "--job-name": None,
                    "--start": None,
                    "--end": None,
                    "--artifact-filter": "*.log",
                    "--output-dir": ".",
                    "--user": "alice",
                    "--codeReviewsURL": "https://gitlab.example/gitlab",
                    "--verifySSL": "True",
                    "--project": "grp",
                    "--repo": "repo",
                    "--ssh_pat_url": "git@example",
                    "--ssh_pat_port": "22",
                }
            )

        self.assertTrue(ret)
        self.assertEqual([("grp", "repo")], fake_host.repo_calls)
        self.assertEqual("123", fake_repo.calls[0]["job_id"])
        self.assertEqual("*.log", fake_repo.calls[0]["artifact_filter"])
        self.assertIsNone(fake_repo.calls[0]["started_after"])
        self.assertIsNone(fake_repo.calls[0]["started_before"])
