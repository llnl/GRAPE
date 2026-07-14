import logging
import os
from datetime import date, datetime, time, timezone

from vine import utility
from vine.option import Option
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.vine_logging import log_wrapper


def parse_cli_datetime(value, *, end_of_day=False):
    if not value:
        return None

    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    has_explicit_time = "T" in normalized or " " in normalized
    if not has_explicit_time:
        parsed_date = date.fromisoformat(normalized)
        parsed_time = time.max if end_of_day else time.min
        return datetime.combine(parsed_date, parsed_time, tzinfo=timezone.utc)

    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class DownloadJobArtifacts(Option, WorkspaceDirHandler):
    """
    grape download_job_artifacts
    Download matching files from GitLab CI job artifacts.
    Usage: grape-download_job_artifacts [--job-id=<id>]
                                        [--job-name=<name>]
                                        [--start=<datetime>]
                                        [--end=<datetime>]
                                        --artifact-filter=<pattern>
                                        [--output-dir=<dir>]
                                        [--user=<userName>]
                                        [--codeReviewsURL=<url>]
                                        [--verifySSL=<bool>]
                                        [--project=<prj>]
                                        [--repo=<repo>]
                                        [--ssh_pat_url=<url>]
                                        [--ssh_pat_port=<int>]

    Options:
        --job-id=<id>              Download artifacts from the specified job identifier instead of searching failed jobs.
        --job-name=<name>          Restrict failed-job searches to jobs with the given name.
        --start=<datetime>         Inclusive start of the search range for failed jobs. Accepts ISO-8601 date or datetime.
        --end=<datetime>           Inclusive end of the search range for failed jobs. Accepts ISO-8601 date or datetime.
        --artifact-filter=<pattern>
                                   Required shell-style glob used to match artifact file names or archive paths.
        --output-dir=<dir>         Directory to extract matching files into.
                                   [default: .]
        --user=<userName>          Your GitLab user name.
        --codeReviewsURL=<url>     The code review platform url, e.g. https://your.host.org/gitlab.
                                   [default: .grapeconfig.project.codeReviewsURL]
        --verifySSL=<bool>         Set to False to ignore SSL certificate verification issues.
                                   [default: .grapeconfig.project.verifySSL]
        --project=<prj>            The top level project (Bitbucket) or group (GitLab) name.
                                   [default: .grapeconfig.project.name]
        --repo=<repo>              The top level repository name.
                                   [default: .grapeconfig.repo.name]
        --ssh_pat_url=<url>        SSH URL for generating Personal Access Tokens to authenticate into a Code Review service's
                                   REST API.
                                   [default: .grapeconfig.repo.ssh_pat_url]
        --ssh_pat_port=<int>       Port number to issue ssh command over to generate a Personal Access Token for authentication
                                   into a Code Review service's REST API.
                                   [default: .grapeconfig.repo.ssh_pat_port]
    """

    def __init__(self):
        super(DownloadJobArtifacts, self).__init__()
        self._key = "download_job_artifacts"
        self._section = "Other"

    def description(self):
        return "Download matching files from GitLab CI job artifacts."

    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_PROJECT)
        config.set(self.SECTION_PROJECT, "codeReviewsURL", "https://your.host.org/gitlab/or/bitbucket")
        config.set(self.SECTION_PROJECT, "verifySSL", "True")
        config.set(self.SECTION_PROJECT, "name", "My unnamed project")
        config.ensureSection(self.SECTION_REPO)
        config.set(self.SECTION_REPO, "ssh_pat_url", "git@gitlab.your.host.org")
        config.set(self.SECTION_REPO, "ssh_pat_port", "7999")
        config.set(self.SECTION_REPO, "name", "My unnamed repo")

    @staticmethod
    def _resolve_time_range(args):
        if args["--job-id"]:
            return None, None

        if bool(args["--start"]) != bool(args["--end"]):
            raise ValueError("--start and --end must be provided together unless --job-id is specified.")

        if not args["--start"]:
            raise ValueError("--start and --end are required unless --job-id is specified.")

        start = parse_cli_datetime(args["--start"], end_of_day=False)
        end = parse_cli_datetime(args["--end"], end_of_day=True)
        if end < start:
            raise ValueError("--end must be greater than or equal to --start.")
        return start, end

    @log_wrapper
    def execute(self, args):
        if "gitlab" not in args["--codeReviewsURL"]:
            logging.info("download_job_artifacts should only be used with GitLab.")
            return False

        try:
            started_after, started_before = self._resolve_time_range(args)
        except ValueError as exc:
            logging.error(str(exc))
            return False
        except Exception as exc:
            logging.error(f"Failed to parse --start/--end: {exc}")
            return False

        if args["--job-id"] and (args["--start"] or args["--end"]):
            logging.info("Ignoring --start/--end because --job-id was specified.")

        user_name = utility.getUserName(args)
        git_host = utility.authenticateToGitHost(user_name, self.workspace_dir, args)
        repo = git_host.repo(args["--project"], args["--repo"])

        downloads = repo.download_job_artifacts(
            artifact_filter=args["--artifact-filter"],
            output_dir=os.path.abspath(args["--output-dir"]),
            job_id=args["--job-id"],
            started_after=started_after,
            started_before=started_before,
            job_name=args["--job-name"],
        )

        if downloads:
            logging.info(f"Downloaded {len(downloads)} artifact file(s) into {os.path.abspath(args['--output-dir'])}")
        else:
            logging.info("No matching artifact files were downloaded.")
        return True
