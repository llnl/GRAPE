import getpass
import fnmatch
import io
import logging
import os
import posixpath
import re
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
try:
    grape_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    sys.path.insert(0, os.path.join(grape_dir, 'python-gitlab'))
    import gitlab
except ModuleNotFoundError:
    # Don't error out here because this is imported even if GitLab is not used
    pass
from vine import config_parser_global
from vine import GrapeKeyring
from vine import utility
from vine.option import Option

GRAPE_GITLAB_APPROVAL_RULE_NAME = "GRAPE Reviewers"
# Grape has the following definitions, most strongly correllated with Bitbucket definitions:
# Project - collection of repositories (roughly analogous to a Gitlab Group)
# Repo - the actual repository (roughly analogous to a Gitlap Project)
class GrapeGitlabAdapter:
    defaultURL = "https://your.host.org/gitlab"
    defaultPort = 7999
    defaultSSH_Path= "git@gitlab.your.host.org"
    defaultCurl = "/usr/bin/curl"
    # default token expiration
    defaultExpiration = 29

    def __init__(self, username=None, url=defaultURL, verify=True, port=defaultPort, ssh_path = defaultSSH_Path, curl = defaultCurl, group = None, *, workspace_dir):

        if username is None:
            self._userName = utility.getUserName(service="Gitlab")
        else:
            self._userName = username

        self.workspace_dir = workspace_dir

        self._service = url
        self._curl = curl
        password = GrapeKeyring.get_password(self._service, self._userName)

        if group is None:
            # If the group is not specified, get it from the .grapeconfig
            group = config_parser_global.grapeConfig().get(Option.SECTION_PROJECT, "name")

        if self.auth(self._service, self._userName, password, port, ssh_path, group, verify=verify):
            self.url = url
            logging.info("Connected to Gitlab.")
        else:
            self._gitlab= None
            logging.info("Could not connect to Gitlab...")

    def generate_personal_access_token(self, port, ssh_url, expires = defaultExpiration):
        command = f"ssh -p {port} {ssh_url} personal_access_token grape_review api {expires}"
        logging.info(f"Generating token by executing {command}")
        completed_process = subprocess.run(command,
                                           capture_output=True,
                                           shell=True)
        return completed_process.stdout.decode().strip().split()[1].strip()

    def auth(self, service, username, password, port, ssh_path, group, verify=True):
        if not verify:
            import warnings
            import urllib3
            warnings.filterwarnings('ignore', category=urllib3.exceptions.InsecureRequestWarning)

        # set a password to something bogus to trigger an authentication error
        if (password is None):
            password = "123456_bad_password"
        self._userName = username
        self._service = service
        if 'GRAPE_GITLAB_ACCESS_TOKEN' in os.environ:
            self._gitlab = gitlab.Gitlab(service, private_token=os.environ['GRAPE_GITLAB_ACCESS_TOKEN'], api_version=4)
        else:
            self._gitlab = gitlab.Gitlab(service, password, api_version=4)
        numAttempts = 0
        success = False
        while numAttempts < 4 and not success:
            try:
                projects = None
                try:
                    projects = self.projectlist()
                except:
                    pass
                if projects:
                    # There may be projects (groups) that are visible to all users, so check for our project (group).
                    if group.lower() in [x.lower() for x in projects]:
                        success = True
                    else:
                        logging.info(f"{group} not accessible. Available groups: {projects}")
                        raise gitlab.exceptions.GitlabAuthenticationError()
                else:
                    logging.info("empty list of gitlab groups.")
                    raise gitlab.exceptions.GitlabAuthenticationError()
            except gitlab.exceptions.GitlabAuthenticationError as e:
                logging.debug(e)
                logging.debug(type(e))
                logging.debug(f"numAttempts is {numAttempts}")
                if numAttempts == 0:
                    logging.info("session expired...")
                    try:
                        GrapeKeyring.set_password(service, self._userName,
                                                  self.generate_personal_access_token(port, ssh_path))
                    except Exception as e:
                        logging.error("Generating personal access token via ssh failed.")
                        logging.error(e)
                        numAttempts += 1
                        continue
                else:
                    logging.info("incorrect username / password...")
                    self._userName = utility.getUserName(self._userName)
                    GrapeKeyring.set_password(service, self._userName,
                                              getpass.getpass("Enter personal access token for " +
                                                              f"{service}: "))
                self._gitlab = gitlab.Gitlab(service,  GrapeKeyring.get_password(service, self._userName), api_version=4, ssl_verify=verify)
                numAttempts += 1

        return success

    def graphQL_query(self, query, dryRun=False):
        token = GrapeKeyring.get_password(self._service, self._userName)
        graphqlurl = f'{self._service}/api/graphql'
        # enable inbound allowlist and add top level repo to list
        data = '\'{ "query": "' + query.replace('"', '\\"') + '" } \''
        # strip newlines from query
        data = re.sub(r' +', ' ', data.replace("\n"," "))
        command = f'{self._curl} {graphqlurl} --header "Authorization: Bearer {token}" --header "Content-Type: application/json" --request POST --data-binary ' + data
        if not dryRun:
            completed_process = subprocess.run(command, capture_output=True, shell=True)
            output = completed_process.stdout.decode().strip()
            return output
        else:
            return command

    # Return list of project names (paths)
    def projectlist(self):
        return [g.path for g in self._gitlab.groups.list(all=True)]

    def project(self, name, min_access_level=None):
        """
        Resolve a GitLab group by name and wrap it in a Project.

        Behavior
        --------
        This helper locates a group returns a `Project` wrapper around the
        corresponding `python-gitlab` Group object. It supports two modes,
        depending on whether a `min_access_level` is provided.

        Parameters
        ----------
        name : str
            The short group name (path) to look up.
            For example, if the project path is "llnl/GRAPE", `name` should be "llnl".
        min_access_level : int or None, optional
            If provided, the lookup is restricted to groups where the current user
            has at least this GitLab access level. Access levels follow GitLab's
            `GitlabAccessLevel` constants, for example:
                10 = Guest
                20 = Reporter
                30 = Developer
                40 = Maintainer
                50 = Owner

            When:
              * `min_access_level is None`:
                  - A single `GET /groups/:path` request is used via
                    `self._gitlab.groups.get(path_with_namespace)`.
                  - This is fast, but the GitLab API does not support a
                    `min_access_level` parameter on this endpoint, so no server-side
                    access-level filtering is applied. You get the group if you can
                    see it at all, or a `GitlabGetError` if you cannot.
              * `min_access_level is not None`:
                  - A group-scoped list call is used:
                        GET /groups?search=...&min_access_level=...
                    via `self._gitlab.groups.list(...)`.
                  - The result is then filtered client-side by exact group name
                    (case-insensitive) and the first matching group id is used.
                  - This is slower, but the `min_access_level` filter is enforced
                    by the GitLab API, so you will not get back groups for which
                    the current user has lower access than requested.

        Returns
        -------
        Project
            A `Project` wrapper around the resolved `Group` instance.

        Raises
        ------
        SystemExit
            If no matching group is found, or if the user does not have sufficient
            access to see the group. In both cases, a message is logged at INFO
            level and the process exits with "Abort".

        Notes
        -----
        - When using the fast path (`min_access_level is None`), subsequent operations
          on the returned `Project` may still fail with GitLab permission errors if the
          current user's access level is insufficient for those specific operations.
        - The slow path relies on `self._gitlab.groups.list` supporting the
          `min_access_level` filter, which is provided by GitLab's groups
          list API. After selecting the group id, a second `self._gitlab.groups.get(id)` call
          fetches the full group object.
        """
        if min_access_level is None:
            # Faster, but does not support min_access_level
            try:
                group = self._gitlab.groups.get(name)
            except gitlab.exceptions.GitlabGetError as e:
                logging.info(f"Could not find group {name}: {e}")
                raise SystemExit("Abort")
        else:
            # Slower, but supports min_access_level
            matching_ids = [x.id for x in self._gitlab.groups.list(all=True, search=name, min_access_level=min_access_level) if x.path.lower() == name.lower()]

            if matching_ids:
                group_id = matching_ids[0]
            else:
                logging.info(f"Could not find group {name}.")
                raise SystemExit("Abort")

            try:
                group = self._gitlab.groups.get(group_id)
            except gitlab.exceptions.GitlabGetError as e:
                logging.info(f"Could not find group {name}: {e}")
                raise SystemExit("Abort")

        return Project(group, self._gitlab)

    def repo(self, project_name, repo_name):
        """
        Retrieve a GitLab project and wrap it in a Repo object.

        This method looks up a GitLab project using the combined
        `project_name/repo_name` path (for example, "llnl/GRAPE"). If the
        project cannot be found or GitLab returns an error, the method will:
          - Log an informational message with the failure reason.
          - Terminate the program by raising SystemExit("Abort").

        Parameters
        ----------
        project_name : str
            The GitLab namespace or group name that owns the project
            (for example, "llnl").
        repo_name : str
            The repository name within the given project or namespace
            (for example, "GRAPE").

        Returns
        -------
        Repo
            A Repo instance that wraps the underlying GitLab project.

        Raises
        ------
        SystemExit
            If the GitLab project cannot be retrieved (for example, it does
            not exist or the user does not have permission).
        """
        path = f'{project_name}/{repo_name}'  # e.g. 'llnl/GRAPE'

        try:
            project = self._gitlab.projects.get(path)
        except gitlab.exceptions.GitlabGetError as e:
            logging.info(f"Could not find project {path}: {e}")
            raise SystemExit("Abort")

        return Repo(project, self._gitlab)


def _truncate_preview(text, limit=100):
    text = ' '.join((text or '').split())
    if len(text) > limit:
        return text[:limit - 3] + '...'
    return text

class Project:
    def __init__(self, gitlab_group, gitlab):
        self.group = gitlab_group
        self.gitlab = gitlab

    def name(self):
        return self.group.name

    def repolist(self):
        return [r.name for r in self.group.projects.list(all=True)]

    def repo(self, name, min_access_level=None):
        """
        Resolve a GitLab project by name within this manager's group and wrap it in a Repo.

        Behavior
        --------
        This helper locates a project under `self.group` and returns a `Repo` wrapper
        around the corresponding `python-gitlab` Project object. It supports two modes,
        depending on whether a `min_access_level` is provided.

        Parameters
        ----------
        name : str
            The short project name (path) to look up within the group.
            For example, if the full path is "llnl/GRAPE", `name` should be "GRAPE".
        min_access_level : int or None, optional
            If provided, the lookup is restricted to projects where the current user
            has at least this GitLab access level. Access levels follow GitLab's
            `GitlabAccessLevel` constants, for example:
                10 = Guest
                20 = Reporter
                30 = Developer
                40 = Maintainer
                50 = Owner

            When:
              * `min_access_level is None`:
                  - A single `GET /projects/:path` request is used via
                    `self.gitlab.projects.get(path_with_namespace)`.
                  - This is fast, but the GitLab API does not support a
                    `min_access_level` parameter on this endpoint, so no server-side
                    access-level filtering is applied. You get the project if you can
                    see it at all, or a `GitlabGetError` if you cannot.
              * `min_access_level is not None`:
                  - A group-scoped list call is used:
                        GET /groups/:id/projects?search=...&min_access_level=...
                    via `self.group.projects.list(...)`.
                  - The result is then filtered client-side by exact project name
                    (case-insensitive) and the first matching project id is used.
                  - This is slower, but the `min_access_level` filter is enforced
                    by the GitLab API, so you will not get back projects for which
                    the current user has lower access than requested.

        Returns
        -------
        Repo
            A `Repo` wrapper around the resolved `Project` instance.

        Raises
        ------
        SystemExit
            If no matching project is found, or if the user does not have sufficient
            access to see the project. In both cases, a message is logged at INFO
            level and the process exits with "Abort".

        Notes
        -----
        - When using the fast path (`min_access_level is None`), subsequent operations
          on the returned `Repo` may still fail with GitLab permission errors if the
          current user's access level is insufficient for those specific operations.
        - The slow path relies on `self.group.projects.list` supporting the
          `min_access_level` filter, which is provided by GitLab's group projects
          list API. After selecting the project id, a second `projects.get(id)` call
          fetches the full project object.
        """
        if min_access_level is None:
            # Faster, but does not support min_access_level
            path = f'{self.group.full_path}/{name}'  # e.g. 'llnl/GRAPE'

            try:
                project = self.gitlab.projects.get(path)
            except gitlab.exceptions.GitlabGetError as e:
                logging.info(f"Could not find project {path}: {e}")
                raise SystemExit("Abort")
        else:
            # Slower, but supports min_access_level
            matching_ids = [x.id for x in self.group.projects.list(all=True, search=name, min_access_level=min_access_level) if x.name.lower() == name.lower()]

            if matching_ids:
                project_id = matching_ids[0]
            else:
                logging.info(f"Could not find project {name}.")
                raise SystemExit("Abort")

            try:
                project = self.gitlab.projects.get(project_id)
            except gitlab.exceptions.GitlabGetError as e:
                logging.info(f"Could not find project {name}: {e}")
                raise SystemExit("Abort")

        return Repo(project, self.gitlab)

    def groupid(self, groupname):
        # groups API doesn't include exact match, so we have to iterate over the search
        for group in self.gitlab.groups.list(all=True, search=groupname):
            if group.name == groupname:
                return group.id
        return 0

    def userid(self, username):
        users = self.gitlab.users.list(all=True, username=username)
        if users:
            return users[0].id
        return 0

class Repo:
    def __init__(self, gitlab_project, gitlab ):
        self.project = gitlab_project
        self.gitlab = gitlab

    @staticmethod
    def _parse_gitlab_datetime(value):
        if not value:
            return None
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @classmethod
    def _job_reference_datetime(cls, job):
        for attr in ("finished_at", "started_at", "created_at"):
            parsed = cls._parse_gitlab_datetime(getattr(job, attr, None))
            if parsed is not None:
                return parsed
        return None

    @classmethod
    def _pipeline_reference_datetime(cls, pipeline):
        for attr in ("updated_at", "finished_at", "created_at"):
            parsed = cls._parse_gitlab_datetime(getattr(pipeline, attr, None))
            if parsed is not None:
                return parsed
        return None

    @staticmethod
    def _artifact_matches_filter(artifact_name, artifact_filter):
        return (
            fnmatch.fnmatchcase(artifact_name, artifact_filter)
            or fnmatch.fnmatchcase(posixpath.basename(artifact_name), artifact_filter)
        )

    @staticmethod
    def _safe_job_dir_name(job):
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", getattr(job, "name", "") or "job").strip("._")
        safe_name = safe_name if safe_name else "job"
        return f"job_{job.id}_{safe_name}"

    @staticmethod
    def _safe_artifact_destination(job_output_dir, artifact_name):
        normalized = os.path.normpath(artifact_name.lstrip("/"))
        if normalized.startswith("..") or os.path.isabs(normalized):
            return None

        destination = os.path.abspath(os.path.join(job_output_dir, normalized))
        if os.path.commonpath([job_output_dir, destination]) != job_output_dir:
            return None
        return destination

    def _find_pipelines_for_job_search(self, started_after, started_before):
        query_parameters = {}
        if started_after:
            query_parameters["updated_after"] = started_after.isoformat()
        if started_before:
            query_parameters["updated_before"] = started_before.isoformat()

        pipelines = self.project.pipelines.list(
            get_all=True,
            per_page=100,
            order_by="updated_at",
            sort="desc",
            query_parameters=query_parameters,
        )
        logging.debug(
            "GitLab returned %d pipeline(s) before job filtering for project %s.",
            len(pipelines),
            getattr(self.project, "path_with_namespace", getattr(self.project, "name", "<unknown>")),
        )
        logging.debug(
            "Requested project pipelines with updated_after=%s, updated_before=%s, order_by=updated_at, "
            "sort=desc, per_page=100.",
            query_parameters.get("updated_after"),
            query_parameters.get("updated_before"),
        )
        return pipelines

    def find_failed_jobs(self, started_after, started_before, job_name=None):
        pipelines = self._find_pipelines_for_job_search(started_after, started_before)
        job_name_regex = re.compile(job_name) if job_name else None
        matching_jobs = []
        for pipeline in pipelines:
            pipeline_time = self._pipeline_reference_datetime(pipeline)
            logging.debug(
                "Inspecting pipeline %s with reference time %s for failed jobs.",
                pipeline.id,
                pipeline_time.isoformat() if pipeline_time else None,
            )

            failed_jobs = pipeline.jobs.list(
                get_all=True,
                per_page=100,
                scope="failed",
            )
            logging.debug(
                "Pipeline %s returned %d failed job(s) before filtering.",
                pipeline.id,
                len(failed_jobs),
            )

            for job in failed_jobs:
                if job_name_regex and not job_name_regex.search(job.name):
                    logging.debug(
                        "Skipping failed job %s (%s): name does not match requested job-name regex %s.",
                        job.id,
                        job.name,
                        job_name,
                    )
                    continue

                job_time = self._job_reference_datetime(job)
                if started_after and (job_time is None or job_time < started_after):
                    logging.debug(
                        "Skipping failed job %s (%s): reference time %s is before start bound %s.",
                        job.id,
                        job.name,
                        job_time.isoformat() if job_time else None,
                        started_after.isoformat(),
                    )
                    continue
                if started_before and (job_time is None or job_time > started_before):
                    logging.debug(
                        "Skipping failed job %s (%s): reference time %s is after end bound %s.",
                        job.id,
                        job.name,
                        job_time.isoformat() if job_time else None,
                        started_before.isoformat(),
                    )
                    continue
                logging.debug(
                    "Matched failed job %s (%s) with reference time %s from pipeline %s.",
                    job.id,
                    job.name,
                    job_time.isoformat() if job_time else None,
                    pipeline.id,
                )
                matching_jobs.append(job)

        matching_jobs.sort(
            key=lambda job: self._job_reference_datetime(job) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        logging.info(
            "Found %d failed job(s) matching the requested filters across %d pipeline(s).",
            len(matching_jobs),
            len(pipelines),
        )
        return matching_jobs

    def _collect_matching_files_from_job(self, job, artifact_filter, output_dir, *, list_only=False):
        job = self.project.jobs.get(int(job.id))
        logging.debug("Inspecting artifact archive for job %s (%s).", job.id, job.name)

        try:
            artifact_bytes = job.artifacts()
        except gitlab.exceptions.GitlabGetError as exc:
            logging.info(f"Unable to download artifacts for job {job.id} ({job.name}): {exc}")
            return []

        try:
            archive = zipfile.ZipFile(io.BytesIO(artifact_bytes))
        except zipfile.BadZipFile:
            logging.info(f"Artifacts for job {job.id} ({job.name}) are not a ZIP archive.")
            return []

        with archive:
            archive_members = [member for member in archive.infolist() if not member.is_dir()]
            logging.debug(
                "Job %s (%s) artifact archive contains %d file(s).",
                job.id,
                job.name,
                len(archive_members),
            )
            if archive_members:
                logging.debug(
                    "First artifact paths for job %s: %s",
                    job.id,
                    ", ".join(member.filename for member in archive_members[:10]),
                )
            matching_members = [
                member for member in archive_members
                if self._artifact_matches_filter(member.filename, artifact_filter)
            ]

            if not matching_members:
                logging.debug(
                    "No artifact files in job %s (%s) matched filter %s.",
                    job.id,
                    job.name,
                    artifact_filter,
                )
                return []

            job_output_dir = os.path.abspath(os.path.join(output_dir, self._safe_job_dir_name(job)))
            logging.debug(
                "Job %s (%s) has %d artifact file(s) matching filter %s.",
                job.id,
                job.name,
                len(matching_members),
                artifact_filter,
            )
            downloaded = []
            for member in matching_members:
                download_info = {
                    "job_id": job.id,
                    "job_name": job.name,
                    "artifact_path": member.filename,
                    "download_path": None,
                    "job_url": getattr(job, "web_url", None),
                }

                if list_only:
                    downloaded.append(download_info)
                    logging.debug(
                        "List-only mode: job %s (%s) would download %s.",
                        job.id,
                        job.name,
                        member.filename,
                    )
                    continue

                destination = self._safe_artifact_destination(job_output_dir, member.filename)
                if destination is None:
                    logging.warning(
                        f"Skipping artifact with unsafe path {member.filename} from job {job.id} ({job.name})."
                    )
                    continue

                utility.ensure_dir(destination)
                with archive.open(member) as source, open(destination, "wb") as target:
                    shutil.copyfileobj(source, target)

                download_info["download_path"] = destination
                downloaded.append(download_info)
                logging.info(f"Downloaded {member.filename} from job {job.id} to {destination}")

        return downloaded

    def download_job_artifacts(self, artifact_filter, output_dir, job_id=None, started_after=None, started_before=None, job_name=None, list_only=False):
        try:
            if job_id:
                jobs = [self.project.jobs.get(int(job_id))]
                logging.info("Found explicit job %s to inspect for matching artifacts.", job_id)
            else:
                jobs = self.find_failed_jobs(started_after, started_before, job_name=job_name)
        except ValueError:
            logging.info(f"Invalid job id: {job_id}")
            return []
        except gitlab.exceptions.GitlabGetError as exc:
            logging.info(f"Unable to find job {job_id}: {exc}")
            return []

        logging.info("Inspecting %d candidate job(s) for artifact matches.", len(jobs))
        downloaded = []
        for job in jobs:
            downloaded.extend(
                self._collect_matching_files_from_job(
                    job,
                    artifact_filter,
                    output_dir,
                    list_only=list_only,
                )
            )
        logging.debug(
            "Matched %d artifact file(s) across %d candidate job(s).",
            len(downloaded),
            len(jobs),
        )
        return downloaded

    def getBranchHeadCommitHash(self, name):
        """
        Get the commit SHA (hash) at the head of a branch.

        Args:
            name (str): Branch name.

        Returns:
            str | None: The head commit SHA if the branch exists; otherwise None if
            the branch is not found.

        Raises:
            gitlab.exceptions.GitlabGetError: If an error other than 404 occurs.
        """
        try:
            return self.project.branches.get(name).commit["id"]
        except gitlab.exceptions.GitlabGetError as e:
            if e.response_code == 404:
                return None
            else:
                raise

    def getFile(self, path, revision):
        """
        Retrieve a file's contents from the repository at a specific revision.

        Args:
            path (str): Repository-relative file path.
            revision (str): Git reference (e.g., branch name, tag, or commit SHA).

        Returns:
            str: UTF-8 decoded file contents if found

        Raises:
            gitlab.exceptions.GitlabAuthenticationError: If authentication is not correct
            gitlab.exceptions.GitlabGetError: If the file could not be retrieved
        """
        return self.project.files.raw(path, revision).decode('utf-8')

    # state can be "all", "merged", "opened", or "closed"
    def pullRequests(self, direction= "IGNORED", at=None, state="opened", target_branch=None, source_branch=None, id=None, reviewer_username=None):
        if id == None:
            # translates from bitbucket to gitlab state types
            state_dict = {"open":"opened", "opened":"opened",
                          "merged": "merged",
                          "declined":"closed", "closed":"closed",
                          "all":"all"
                          }
            state = state_dict[state.lower()]
            if reviewer_username:
                mrs = self.project.mergerequests.list(all=True, state=state, target_branch=target_branch, source_branch=source_branch, reviewer_username=reviewer_username)
            else:
                mrs = self.project.mergerequests.list(all=True, state=state, target_branch=target_branch, source_branch=source_branch)
            return [PullRequest(x, self.gitlab) for x in mrs]
        else:
            return [PullRequest(self.project.mergerequests.list(iids=[id])[0], self.gitlab)]

    def getOpenPullRequest(self, source, target):
        requests = self.pullRequests(state="opened", target_branch=target, source_branch=source)
        return requests[0] if requests else None

    def getMergedPullRequests(self, source, target):
        return self.pullRequests(state="merged", target_branch=target, source_branch=source)

    def createPullRequest(self, title, branch, target_branch, description=None, reviewers=None, non_approvers=None, wip=None, labels=[]):
         # GitLab can create merge requests with no commits, but we don't want those,
         # in the case that the branch is behind the target branch.
         # Check that the branch actually has new commits compared to the target.
         try:
            diff_result = self.project.repository_compare(target_branch, branch, straight=True, per_page=1)
            if diff_result and not diff_result["commits"]:
               logging.info(f"Not creating merge request for {self.project.name}: {target_branch}..{branch} has no commits.")
               return None
         except gitlab.exceptions.GitlabGetError:
            # If the diff is too big, this comparison can throw an exception.
            # In this case, just create the merge request.
            pass

         mr = PullRequest(self.project.mergerequests.create({"source_branch": branch,
                                            "target_branch": target_branch,
                                            "remove_source_branch": False,
                                            "title": PullRequest.get_title_for_wip_state(title, wip)}),
                          self.gitlab)
         mr.update(title,
                   description=description,
                   reviewers=reviewers,
                   non_approvers=non_approvers,
                   wip=wip,
                   add_labels=labels)

         return mr

    def getTag(self, name):
        """
        Retrieve a git tag from the repository by its name.

        Args:
            name (str): The name of the tag to retrieve.

        Returns:
            ProjectTag | None: ProjectTag object if the tag exists; otherwise None

        Notes:
            Throws exception if the tag cannot be retrieved (e.g. unauthorized).
            Does not throw if the tag does not exist.
        """
        try:
            return self.project.tags.get(name)
        except gitlab.exceptions.GitlabGetError as e:
            if e.response_code == 404 and e.error_message == '404 Tag Not Found':
                return None
            else:
                raise

    def createTag(self, name, ref, message):
        """
        Create a git tag in the repository.

        Args:
            name (str): The name of the tag to create.
            ref (str): The commit SHA or branch the tag should point to.
            message (str): The tag message.

        Notes:
            Throws exception if the tag cannot be created.
        """
        self.project.tags.create({'tag_name': name,
                                  'ref': ref,
                                  'message': message})

    def deleteTag(self, name):
        """
        Delete a git tag from the repository by its name.

        Args:
            name (str): The name of the tag to delete.

        Returns:
            None

        Notes:
            Throws exception if the tag cannot be deleted (e.g. unauthorized).
            Does not throw if the tag does not exist.
        """
        try:
            self.project.tags.delete(name)
        except gitlab.exceptions.GitlabDeleteError as e:
            if e.response_code == 404 and e.error_message == '404 Tag Not Found':
                return
            else:
                raise

    def updateTag(self, name, ref, message):
        """
        Updates a git tag in the repository.

        Args:
            name (str): The name of the tag to update.
            ref (str): The commit SHA or branch the tag should point to.
            message (str): The tag message.

        Notes:
            There is no API for updating a tag, so it must be deleted
            (if present) and then recreated with the new ref and message.
            Throws exception if the existing tag cannot be deleted or
            the new tag cannot be created.
        """
        self.deleteTag(name)
        self.createTag(name, ref, message)

    def getDiffs(self, fromRevision, toRevision):
        """
        Compare two revisions in the repository and return their diff/compare data.

        Args:
            fromRevision (str): The base git reference (e.g., branch, tag, or commit SHA).
            toRevision (str): The head git reference (e.g., branch, tag, or commit SHA).

        Returns:
            dict: The GitLab compare API response, including commit and diff information.

        Raises:
            gitlab.exceptions.GitlabGetError: If the comparison cannot be retrieved.
        """
        return self.project.repository_compare(fromRevision, toRevision)

    # If restrict_id is positive, it is the group id to restrict the branch to;
    # if it is negative, it is the negative of the user id to restrict the branch to;
    # otherwise, the push_access_level and merge_access_level are used.
    def setProtectedBranch(self, name, push_access_level, merge_access_level, restrict_id, allow_force_push):
        replaced = False
        # Remove the old protected branch if it already exists
        if self.project.protectedbranches.list(all=True, search=name):
           self.project.protectedbranches.delete(name)
           replaced = True
        createArgs = {"name": name, "allow_force_push": allow_force_push}
        if restrict_id > 0:
           # protect by group
           if push_access_level != 0:
              createArgs["allowed_to_push"] = [{"group_id": restrict_id}]
           else:
              createArgs["push_access_level"] = 0
           if merge_access_level != 0:
              createArgs["allowed_to_merge"] = [{"group_id": restrict_id}]
           else:
              createArgs["merge_access_level"] = 0
        elif restrict_id < 0:
           # protect by user
           if push_access_level != 0:
              createArgs["allowed_to_push"] = [{"user_id": -restrict_id}]
           else:
              createArgs["push_access_level"] = 0
           if merge_access_level != 0:
              createArgs["allowed_to_merge"] = [{"user_id": -restrict_id}]
           else:
              createArgs["merge_access_level"] = 0
        else:
           # protect by access level
           createArgs["push_access_level"] = push_access_level
           createArgs["merge_access_level"] = merge_access_level
        self.project.protectedbranches.create(createArgs)
        return replaced

    @staticmethod
    def printScheduledPipeline(pipeline):
        active = "Active" if pipeline.active else "Inactive"
        print(f"{pipeline.description} ({active})")
        print(f"  id: {pipeline.id}  ref: {pipeline.ref}")
        print(f"  owner: {pipeline.owner['username']} ({pipeline.owner['name']})")
        print(f"  cron: {pipeline.cron}  timezone: {pipeline.cron_timezone}")
        print()

    def getScheduledPipeline(self, pid):
        scheduled_pipelines = self.project.pipelineschedules.list(all=True)
        for pipeline in scheduled_pipelines:
            if pipeline.id == int(pid):
               return pipeline
        return None

    def listScheduledPipelines(self):
        scheduled_pipelines = self.project.pipelineschedules.list(all=True)
        print()
        for pipeline in scheduled_pipelines:
            self.printScheduledPipeline(pipeline)

    def addScheduledPipeline(self, ref, desc, cron, timezone, active):
        args = { "ref": ref, "description": desc, "cron": cron }
        if timezone:
            args["cron_timezone"] = timezone
        if active is not None:
            args["active"] = active
        try:
           pipeline = self.project.pipelineschedules.create(args)
           logging.info("*** Created new pipeline ***")
           self.printScheduledPipeline(pipeline)
        except Exception as e:
            logging.info(f"Failed to create pipeline with {args}.\n{e}")

    def deleteScheduledPipeline(self, pid):
        pipeline = self.getScheduledPipeline(pid)
        logging.info("*** Deleting ***")
        self.printScheduledPipeline(pipeline)
        try:
           self.project.pipelineschedules.delete(pid)
           logging.info("*** Done ***")
        except Exception as e:
           logging.info(f"Failed to delete pipeline {pid} owned by {pipeline.owner['username']}.\n{e}")

    def takeScheduledPipeline(self, pid):
        pipeline = self.getScheduledPipeline(pid)
        logging.info("*** Taking ownership of pipeline ***")
        self.printScheduledPipeline(pipeline)
        try:
           pipeline.take_ownership()
           logging.info("*** Done ***")
        except Exception as e:
           logging.info(f"Failed to take ownership of pipeline {pid} owned by {pipeline.owner['username']}.\n{e}")

    def updateScheduledPipeline(self, pid, ref, desc, cron, timezone, active):
        pipeline = self.getScheduledPipeline(pid)
        if not pipeline:
           logging.info(f"No scheduled pipeline with pid {pipelineid} found! Use grape gitlab-admin --scheduledPipelines=list to list pipelines")
        else:
           logging.info("*** Original ***")
           self.printScheduledPipeline(pipeline)
           orig = [pipeline.ref, pipeline.description, pipeline.cron, pipeline.cron, pipeline.cron_timezone, pipeline.active]
           if ref:
               pipeline.ref = ref
           if desc:
               pipeline.description = desc
           if cron:
               pipeline.cron = cron
           if timezone:
               pipeline.cron_timezone = timezone
           if active is not None:
               pipeline.active = active
           try:
               pipeline.save()
               pipeline._get_updated_data()
               if orig == [pipeline.ref, pipeline.description, pipeline.cron, pipeline.cron, pipeline.cron_timezone, pipeline.active]:
                  logging.info("*** No change ***")
               else:
                  logging.info("*** Updated ***")
                  self.printScheduledPipeline(pipeline)
           except Exception as e:
               logging.info(f"Failed to update pipeline {pid} owned by {pipeline.owner['username']}.\n{e}")

    # Get the pipeline ID corresponding to the last successful job on each merge request
    def listLastSuccessfulPipelines(self, job_name):
        open_merge_requests = self.project.mergerequests.list(all=True, state='opened')
        rows = []
        for mr in open_merge_requests:
           merge_request_iid = mr.iid
           # The pipelines are listed (by default) by creation date in descending order (newest first)
           branch_pipelines = self.project.pipelines.list(all=True, ref=f"refs/merge-requests/{merge_request_iid}/merge")
           for pi in branch_pipelines:
               found = False
               for job in pi.jobs.list(all=True, scope="success"):
                  if job.name == job_name:
                     rows.append(f"{pi.id}\t{pi.ref}")
                     found = True
                     break
               if found:
                  # Only consider the successful job on the newest pipeline
                  break
        if rows:
           print(f"Last successful runs of {job_name}:")
           print("PID\tREF") 
           for row in rows:
               print(row)
        else:
           print(f"No successful runs of {job_name}")

    def listRunningJobs(self, name, op):
        for pi in self.project.pipelines.list(all=True, scope='running'):
            for job in pi.jobs.list(all=True):
               if job.status in ['waiting_for_resource', 'preparing', 'pending', 'running'] and job.user['username'] == name:
                  print(f"#{job.id} {job.status} {job.name} {job.ref} {job.runner['description'] if job.runner else ''} {job.started_at if job.started_at else ''}")
                  if op == 'log':
                     pjob = self.project.jobs.get(job.id)
                     print(pjob.trace().decode())

    # Run named job on specified pipeline
    def runJob(self, job_name, pid, allow_rerun):
        branch_pipelines = self.project.pipelines.list(all=True)
        foundPipe = False
        foundJob = False
        for pi in branch_pipelines:
            if pi.id == int(pid):
               foundPipe = True
               for pipeline_job in pi.jobs.list(all=True):
                  if pipeline_job.name == job_name:
                     foundJob = True
                     print(f"Found job {job_name} on pipeline for {pi.ref}")
                     job = self.project.jobs.get(pipeline_job.id, lazy=True)
                     if allow_rerun or pipeline_job.status != 'success':
                        print(f"Previous status: {pipeline_job.status}")
                        try:
                           print(f"Running {job_name}...")
                           job.play()
                           print("Done")
                        except Exception as e:
                           logging.info(f"Failed to run job {job_name} on pipeline {pid}\n{e}")
                     else:
                        print("Job already succeeded, not running")
                     break
        if not foundPipe:
            logging.info(f"Failed to find pipeline {pid}")
        elif not foundJob:
            logging.info(f"Failed to find job {job_name} on pipeline {pid}")

    def getSuccessfulJob(self, job_name, current_sha, target_sha, current_branch, target_branch):
        # manual jobs will have the branch name as a reference
        successful_job = None
        job_name = job_name.strip()
        branch_pipelines = self.project.pipelines.list(all=True, ref=current_branch)
        logging.debug(f"BRANCH PIPELINES {branch_pipelines}")
        # if there is a pipeline matching the current branch...
        for pi in branch_pipelines:
            logging.debug(pi.__dict__)
            # ... that has a successful job
            for job in pi.jobs.list(all=True, scope="success"):
               logging.debug(f"SUCCESSFUL branch pipeline : {pi.ref}, {pi.iid}, {pi.sha}\n\n")
               logging.debug(f"checking {job.name} against {job_name}")
               # ... matching the job name the user asked for
               if job.name == job_name:
                   logging.debug(f"checking {job.commit['id']} against {current_sha}")
                   # ... that ran aginst the current commit on this branch
                   if job.commit["id"] == current_sha:
                       # then the job passed!
                       logging.debug(f"creating successful_job")
                       successful_job = Job(self.project, job.id, self.gitlab)
                       break

        # merge request jobs will have a reference based off the merge request iid
        merge_request = self.getOpenPullRequest(current_branch, target_branch)
        logging.debug(f"open merge request {merge_request}")
        if merge_request and successful_job == None:
            merge_request_iid = merge_request.iid()
            merge_pipelines = self.project.pipelines.list(all=True, ref=f"refs/merge-requests/{merge_request_iid}/merge")
            logging.debug(f"MERGE_PIPELINES {merge_pipelines}")
            #if there is a pipeline in a repo configured to run merge requests under proposed merges...
            for pi in merge_pipelines:
                # ... that contains a successful job...
                for job in pi.jobs.list(all=True, scope="success"):
                   logging.debug(f"SUCCESSFUL job in merge_pipeline : {pi.ref}, {pi.iid}, {pi.sha}\n\n")
                   logging.debug(f"checking {job.name} against {job_name}")
                   # ... whose name matches the one the user cares about...
                   if job.name == job_name:
                       logging.debug(f"{job.commit}")
                       # ... and was actually tested agains the merge of this commit and the target commit...
                       parents = job.commit["parent_ids"]
                       logging.debug(f"checking {parents} against {current_sha} and {target_sha}")
                       if current_sha in parents and target_sha in parents:
                           # ...then the job passed!
                           logging.debug(f"creating successful_job")
                           successful_job = Job(self.project, job.id, self.gitlab)
                           break
            if successful_job == None:
                #if there is a pipeline in a repo configured to run merge requests on head..."
                head_pipelines = self.project.pipelines.list(all=True, ref=f"refs/merge-requests/{merge_request_iid}/head")
                for pi in head_pipelines:
                    # ... that contains a successful job...
                    for job in pi.jobs.list(all=True, scope="success"):
                       logging.debug(f"SUCCESSFUL job in head_pipeline : {pi.ref}, {pi.iid}, {pi.sha}\n\n")
                       logging.debug(f"checking {job.name} against {job_name}")
                       # ... whose name matches the one the user cares about...
                       if job.name == job_name:
                           logging.debug(f"{job.commit}")
                           # ... and was actually tested agains the merge of this commit and the target commit...
                           sha = job.commit["id"]
                           logging.debug(f"checking {sha} against {current_sha}")
                           if current_sha ==  sha:
                               # ...then the job passed!
                               logging.debug(f"creating successful_job")
                               successful_job = Job(self.project, job.id, self.gitlab)
                               break


        else:
            logging.debug(f"MR not found")

        return successful_job

    def artifact(self, ref_name, artifact_path, job):
        return self.project.artifact(ref_name,artifact_path, job)

    def addToMergeTrain(self, merge_request, sha):
        """
        Add the given pull request to the GitLab merge train for this project.

        This method sends a POST request to the GitLab API to enqueue the
        specified merge request into the project's merge train.

        Parameters
        ----------
        merge_request : Any
            An object representing the merge request. It must provide an `iid()`
            method that returns the internal ID of the merge request in GitLab.
        sha : str
            The SHA must match the HEAD of the merge request branch, otherwise
            the merge fails.

        Side Effects
        ------------
        Sends an HTTP POST request to the GitLab API endpoint:
        `/projects/{project_id}/merge_trains/merge_requests/{iid}`

        The request body includes:
            {
                "sha": "<provided sha>"
            }

        The call is expected to be made via `self.gitlab.http_post`.

        Raises
        ------
        Any exception that `self.gitlab.http_post` may raise in case of
        network errors, authentication failures, or non-successful responses.

        Notes
        -----
        Adapted from https://github.com/python-gitlab/python-gitlab/pull/2552.
        """
        path = f"/projects/{self.project.id}/merge_trains/merge_requests/{merge_request.iid()}"

        data = {
            "sha": sha
        }

        self.gitlab.http_post(path, post_data=data)




class Job:
    def __init__(self, gitlab_project, gitlab_job_id, gitlab):
        self.job = gitlab_project.jobs.get(gitlab_job_id)
        self.gitlab = gitlab
    def artifact(self, path):
        return self.job.artifact(path)
    
        
        

class PullRequest:
    """
    node is the dictionary with the state of the Pull Request.
    stashy_pull_requests is the stashy object needed to update the pull request.
    """
    def __init__(self, gitlab_mergerequest, gitlab):
        self.mergerequest = gitlab_mergerequest
        self.gitlab = gitlab

    def author(self):
        return self.mergerequest.author["username"]

    def authorName(self):
        return self.mergerequest.author["name"]

    def authorEmail(self):
        authorID = self.mergerequest.author["id"]
        # This will only return a non-empty value if the public email has been set
        return self.gitlab.users.get(authorID).public_email

    def description(self):
        description = self.mergerequest.description or ""
        # Drop non-ascii characters
        return description.encode('ascii', 'ignore').decode('ascii')

    def date(self):
        return self.mergerequest.created_at

    def reviewers(self):
        """
        Returns [(username,bool(approved),displayname)...]
        """

        ret = {}

        for approver in self.mergerequest.reviewers:
            ret[approver["username"]] = (approver["username"], False, approver["name"])

        approvals = self.mergerequest.approvals.get()
        for reviewer in approvals.approved_by:
            name = reviewer["user"]["username"]
            if name in ret:
                ret[name] = (ret[name][0],True,ret[name][2])

        return list(ret.values())

    def labels(self):
        return self.mergerequest.labels

    def state(self):
        return self.mergerequest.state

    def title(self):
        return self.mergerequest.title

    def fromRef(self):
        return self.mergerequest.source_branch

    def toRef(self):
        return self.mergerequest.target_branch

    def fromSHA(self):
        return self.mergerequest.sha

    def commits(self):
        """
        Return all commits associated with this merge request.

        Returns
        -------
        List[ProjectCommit]
            A list of `ProjectCommit` objects for this merge request, in the order
            returned by the GitLab API (appears to be newest to oldest).
        """
        return self.mergerequest.commits(get_all=True)

    def approve(self):
        """
        Approve this merge request.

        Returns:
            The GitLab API response from the approve action.

        Notes:
            Returns None if authentication failed (including already approved).
        """
        try:
            return self.mergerequest.approve()
        except gitlab.exceptions.GitlabAuthenticationError as e:
            try:
                # authenticate to ensure that the user info is populated
                self.gitlab.auth()
                username = self.gitlab.user.username
                approvals = self.mergerequest.approvals.get()
                for reviewer in approvals.approved_by:
                    if username == reviewer["user"]["username"]:
                        logging.info(f'User {username} already approved merge request.')
                        return None
            except:
                pass

            logging.error(f'GRAPE: ERROR: User not authorized to approve merge request: {e}')
            return None


    def approved(self):
        approvals = self.mergerequest.approvals.get()
        return approvals.approvals_required > 0 and approvals.approvals_left == 0

    def link(self):
        url = self.mergerequest.web_url

        if not isinstance(url, str):
            url = url.decode("utf-8")

        return url


    def version(self):
        # gitlab does not seem to have the same concept of a version exposed to the REST API
        return 123

    def iid(self):
        return self.mergerequest.iid

    def diffs(self):
        """
        Retrieve the list of all diffs for the current merge request.

        Returns
        -------
        list
            A list of dictionaries, each representing a diff and containing
            entries such as "diff", "old_path", and "new_path". It appears
            there is one diff dictionary per changed file.

        Notes:
            We do not use self.mergerequest.changes() because it uses a
            deprecated endpoint. The correct endpoint is not exposed in
            the python-gitlab library as of v7.1.0.
        """
        path = f"{self.mergerequest.manager.path}/{self.mergerequest.encoded_id}/diffs"
        return self.gitlab.http_list(path, get_all=True)

    def unresolved_threads(self, ignored_commenters=None):
        """
        Return printable notes from unresolved merge request discussions.

        Parameters
        ----------
        ignored_commenters : Iterable[str] | None, optional
            Comment author names/usernames to exclude from the returned notes.
            Matching is case-insensitive. System notes are always excluded.

        Returns
        -------
        list[dict]
            Each item contains:
              - id: discussion id
              - path: file path for diff discussions, or None
              - line: line number for diff discussions, or None
              - notes: list of note dictionaries with author, created_at, and body
        """
        ignored_commenters = {
            commenter.lower() for commenter in (ignored_commenters or set()) if commenter
        }
        unresolved_threads = []
        discussions = list(self.mergerequest.discussions.list(get_all=True))
        merge_request_label = self.link()

        logging.debug(
            f'Inspecting {len(discussions)} merge request discussion(s) for {merge_request_label}'
        )

        for discussion in discussions:
            # `discussion.asdict()` exposes the `notes`, `resolved`, and
            # `resolvable` fields returned by GitLab's discussions API:
            # https://docs.gitlab.com/api/discussions/#list-project-merge-request-discussion-items
            discussion_data = discussion.asdict()
            discussion_id = discussion_data.get('id')
            discussion_resolved = discussion_data.get('resolved', True)
            resolvable = discussion_data.get('resolvable')
            discussion_notes = discussion_data.get('notes', [])
            discussion_has_unresolved_note = False

            logging.debug(
                f'  Discussion {discussion_id}: resolved={discussion_resolved}, '
                f'resolvable={resolvable}, notes={len(discussion_notes)}'
            )

            path = None
            line = None
            notes = []

            for note in discussion_notes:
                body = (note.get('body') or '').strip()
                is_system = note.get('system')
                note_resolved = note.get('resolved')
                note_resolvable = note.get('resolvable')
                body_preview = _truncate_preview(body)

                logging.debug(
                    f'    Note in discussion {discussion_id}: system={is_system}, '
                    f'body_empty={not body}, '
                    f'resolved={note_resolved}, '
                    f'resolvable={note_resolvable}, '
                    f'preview={body_preview or "<empty>"}'
                )

                if not is_system and note_resolvable and note_resolved is False:
                    discussion_has_unresolved_note = True

                if note.get('system'):
                    continue

                position = note.get('position') or {}

                if path is None:
                    path = position.get('new_path') or position.get('old_path')

                if line is None:
                    line = position.get('new_line') or position.get('old_line')

                if not body:
                    continue

                author = note.get('author') or {}
                author_name = author.get('username') or author.get('name') or 'unknown'

                if author_name.lower() in ignored_commenters:
                    logging.debug(
                        f'    Note in discussion {discussion_id}: filtered out for ignored commenter {author_name}'
                    )
                    continue

                notes.append({
                    'author': author_name,
                    'created_at': note.get('created_at'),
                    'body': body
                })

            discussion_is_unresolved = (not discussion_resolved) or discussion_has_unresolved_note

            if discussion_resolved and discussion_has_unresolved_note:
                logging.debug(
                    f'  Discussion {discussion_id} is marked resolved at the discussion level, '
                    f'but has at least one unresolved resolvable note. Treating it as unresolved.'
                )

            if discussion_is_unresolved and notes:
                unresolved_threads.append({
                    'id': discussion_data.get('id'),
                    'path': path,
                    'line': line,
                    'notes': notes
                })

        logging.debug(
            f'Collected {len(unresolved_threads)} unresolved discussion thread(s) with printable comments for {merge_request_label}'
        )
        return unresolved_threads

    @staticmethod
    def get_title_for_wip_state(title, wip):
        if not hasattr(PullRequest.get_title_for_wip_state, "regexp"):
            PullRequest.get_title_for_wip_state.regexp = re.compile(r'^(wip:|draft:)\s*', re.IGNORECASE)

        new_title = title

        if wip is not None:
            if wip:
                if not PullRequest.get_title_for_wip_state.regexp.match(title):
                    new_title = "Draft: " + title
            else:
                new_title = PullRequest.get_title_for_wip_state.regexp.sub('', title)

        return new_title

    # reviewers is a dict, keyed by approval rule name, valued by lists of usernames
    def update(self, ver, title=None, description=None, reviewers=None, non_approvers=None, wip=None, add_labels=[], remove_labels=[]):
        if title is None:
            title = self.mergerequest.title

        self.mergerequest.title = self.get_title_for_wip_state(title, wip)

        if description:
            self.mergerequest.description = description

        if reviewers:
            all_reviewer_ids = set()

            for review_rule_name in reviewers:
                reviewer_group = reviewers[review_rule_name]
                approval_rule_name = reviewer_group['label']
                users = reviewer_group['reviewers']
                num_required = len(users)

                approval_rules = self.mergerequest.approval_rules.list()

                # Find the approval rule by name
                matching_rule = None

                for rule in approval_rules:
                    if rule.name == approval_rule_name:
                        matching_rule = rule
                        break

                # Merge request approvals created by others can only be changed by maintainer and above,
                # so only update them if they are changed and just warn if they cannot be updated.

                if users:
                    rule_reviewer_ids = []

                    for r in users:
                        matching_reviewers = self.gitlab.users.list(all=True, username=r)
                        if matching_reviewers:
                            gitlab_reviewer = matching_reviewers[0]
                        else:
                            logging.info(f"Could not find reviewer {r}.")
                            raise SystemExit("Abort")
                        if non_approvers and r in non_approvers:
                            logging.info(f"Reviewer {r} is a non-approver, not adding to {approval_rule_name}.")
                            num_required -= 1
                            all_reviewer_ids.add(gitlab_reviewer.id)
                        else:
                            rule_reviewer_ids.append(gitlab_reviewer.id)

                    update = True
                    if matching_rule is not None:
                        eligible_approver_ids = set()
                        for approver in matching_rule.eligible_approvers:
                            eligible_approver_ids.add(approver["id"]) 
                        if eligible_approver_ids == set(rule_reviewer_ids) and matching_rule.approvals_required == num_required:
                            logging.info(f'Approval rule "{approval_rule_name}" unchanged.')
                            update = False 
                    if not rule_reviewer_ids and num_required == 0:
                        logging.info(
                            f'Approval rule "{approval_rule_name}" has no approvers after filtering non-approvers. '
                            "Skipping empty rule creation."
                        )
                        update = False
                    if update:
                        try:
                            self.mergerequest.approvals.set_approvers(num_required,approver_ids=rule_reviewer_ids, approval_rule_name=approval_rule_name)
                        except gitlab.exceptions.GitlabCreateError as e:
                            logging.warning(f'GRAPE: WARNING: Failed to create approval rule "{approval_rule_name}": {e}')
                        except gitlab.exceptions.GitlabUpdateError as e:
                            logging.warning(f'GRAPE: WARNING: Failed to update approval rule "{approval_rule_name}": {e}')

                    for reviewer_id in rule_reviewer_ids:
                        all_reviewer_ids.add(reviewer_id)
                else:
                    if matching_rule is not None:
                        try:
                            # Delete the approval rule
                            self.mergerequest.approval_rules.delete(matching_rule.id)
                            logging.info(f'Deleted approval rule "{approval_rule_name}".')
                        except gitlab.exceptions.GitlabDeleteError as e:
                            logging.warning(f'GRAPE: WARNING: Failed to delete approval rule "{approval_rule_name}": {e}')

            self.mergerequest.reviewer_ids = list(all_reviewer_ids)

        if self.mergerequest.description:
            self.mergerequest.description = re.sub(r"([^\n])\n([^\n])", r"\1\n\n\2", self.mergerequest.description)

        labels = set(self.mergerequest.labels)
        for label in add_labels:
            labels.add(label)
        for label in remove_labels:
            try:
               labels.remove(label)
            except KeyError:
               pass
        self.mergerequest.labels = list(labels)

        # Disable removal of source branch on merge (if this merge request was created by hand).
        # This should only affect merging by clicking the merge button (grape manually disables the removal when
        # when merging the merge request). The merge button should be disabled by disabling CI and requiring pipelines
        # to succeed, but disabling it here provides another layer of protection (removing the branch early can
        # adversely affect tagging and notification steps in multi-repo projects).
        self.mergerequest.remove_source_branch = False
        self.mergerequest.save()
        return self

    def regeneratePipeline(self, raiseOnFailure=True):
        # Create a new pipeline to reflect any changes in labels
        try:
            self.mergerequest.pipelines.create()
        except gitlab.exceptions.GitlabCreateError:
            time.sleep(5)
            logging.info("Trying again after initial 405 error...")
            try:
                self.mergerequest.pipelines.create()
            except gitlab.exceptions.GitlabCreateError as e:
                if raiseOnFailure:
                    raise(e)

    def __eq__(self, other):
        return (self.toRef() == other.toRef()) and (self.fromRef() == other.fromRef())

    def __str__(self):
        all_reviewers = ', '.join(r[0] + " (%s)" % ("Approved" if r[1] else "Not yet approved") for r in self.reviewers())
        return f"Title: {self.title()}\n" + \
               f"From: {self.fromRef()}\n" + \
               f"To: {self.toRef()}\n" + \
               f"Reviewers: {all_reviewers}\n" + \
               f"Description: {self.description()}\n"

    def merge(self, merge_commit_message=None, should_remove_source_branch=False, merge_when_pipeline_succeeds=False):
        try:
            self.mergerequest.merge(merge_commit_message=merge_commit_message,
                                    should_remove_source_branch=should_remove_source_branch,
                                    merge_when_pipeline_succeeds=merge_when_pipeline_succeeds)
            return True
        except gitlab.exceptions.GitlabMRClosedError as e:
            logging.info(f"GitlabMRClosedError triggered! {e.__dict__}") 
            raise e

def testMe():
    grape_gitlab = GrapeGitlabAdapter(workspace_dir=os.getcwd())
    logging.info(f"\nPROJECT:{p}")
    project = grape_gitlab.project("GRP")
    reponames = project.repolist()
    for reponame in reponames:
        logging.info(f" REPONAME{reponame}")
        try:
            repo = project.repo(reponame)
            for pull in repo.pullRequests(state="open"):
                logging.info(f"  TITLE:     {pull.title()}")
                logging.info(f"  STATE:     {pull.state()}")
                logging.info(f"  AUTHOR:    {pull.author()}")
                logging.info(f"  AUTHORNAME:{pull.authorName()}")
                logging.info(f"  DATE:      {pull.date()}")
                logging.info(f"  REVIEWERS: {pull.reviewers()}")
                logging.info(f"  FROM:      {pull.fromRef()}")
                logging.info(f"  TO:        {pull.toRef()}")
                logging.info(f"  DESC:      {pull.description()}")
                logging.info(f"  APPROVED:  {pull.approved()}")
                logging.info(f"  LINK:      {pull.link()}\n")
#                    logging.info(f"  MERGE success {pull.merge()}")
            logging.info("GETTING OPEN PULL REQUEST")
            pull = repo.getOpenPullRequest("feature/probinso/gitlab_support","develop")
            logging.info(f"  TITLE:     {pull.title()}")
            logging.info(f"  REVIEWERS: {pull.reviewers()}")
            logging.info(f"  APPROVED:  {pull.approved()}")

        except:
            pass


if __name__ == "__main__":
    testMe()
