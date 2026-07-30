import logging
import re
from vine import config_parser_global
from vine import grape_errors
from vine import grapeGit as git
from vine import multi_repo_cmd_launcher
from vine.option import Option
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.vine_logging import log_wrapper


class Push(Option, WorkspaceDirHandler):
    """
    grape push pushes your current branch to origin for your outer level repo and all subprojects.
    it uses 'git push -u origin <branch>' for the git command.

    Usage: grape-push [--noTopLevel] [--noRecurse] [--noRecurseSubprojects] [--pushAll] [--quietRemoteMessages]

    Options:
        --noTopLevel            Don't perform push in top level repo.
        --noRecurse             Don't perform pushes in submodules.
        --noRecurseSubprojects  Don't perform pushes in nested subprojects.
        --pushAll               Push all repositories regardless of whether local is ahead of origin.
        --quietRemoteMessages   Suppress `remote: ...` messages and GitLab review hints from git push output.

    """
    def __init__(self):
        super(Push, self).__init__()
        self._key = "push"
        self._section = "Workspace"

    def description(self):
        return "Pushes your current branch to origin in all projects in this workspace."

    @log_wrapper
    def execute(self, args):
        quiet_remote_messages = args.get("--quietRemoteMessages", False)
        push_args = dict(args)
        push_args["_accumulateRemoteMessages"] = not quiet_remote_messages
        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
            push,
            skipSubmodules=args["--noRecurse"],
            runInSubprojects=not args["--noRecurseSubprojects"],
            runInOuter=not args["--noTopLevel"],
            workspace_dir=self.workspace_dir,
            globalArgs=push_args)
        retvals = launcher.launchFromWorkspaceDir(handleMRE=handlePushMRE)

        if not any(pushSucceeded(retval) for retval in retvals):
            logging.info("No repositories were pushed to origin. Local repos are up to date.")
        else:
            logging.info("Pushed current branch to origin")
            if not quiet_remote_messages:
                logCollectedRemoteMessages(retvals)
        return True

    def setDefaultConfig(self, config):
        pass


class PushResult:
    """Result for a single repository push.

    Attributes:
        pushed (bool): True when the repository branch was pushed.
        repo (str): Repository path where the push was attempted.
        branch (str): Branch that was pushed or checked for push eligibility.
        output (str): Combined git push output captured for later reporting.
    """

    def __init__(self, pushed, repo='', branch='', output=''):
        self.pushed = pushed
        self.repo = repo
        self.branch = branch
        self.output = output or ''

    def __bool__(self):
        return self.pushed

    def __eq__(self, other):
        if isinstance(other, bool):
            return self.pushed == other
        if isinstance(other, PushResult):
            return (self.pushed == other.pushed and
                    self.repo == other.repo and
                    self.branch == other.branch and
                    self.output == other.output)
        return NotImplemented

    def __repr__(self):
        return (f"PushResult(pushed={self.pushed!r}, repo={self.repo!r}, "
                f"branch={self.branch!r}, output_length={len(self.output)})")


REMOTE_LINE_RE = re.compile(r"^\s*remote:\s?(.*)$", re.IGNORECASE)
CREATE_MERGE_REQUEST_RE = re.compile(
    r"\b(?:to\s+)?create\s+a\s+merge\s+request\b",
    re.IGNORECASE)
URL_RE = re.compile(r"https?://\S+")


def pushSucceeded(retval):
    """Determines whether a multi-repo push return value means "pushed".

    Args:
        retval: Return value from a repository push command. New callers return
            PushResult, while older or mocked callers may still return bool.

    Returns:
        bool: True when the repository was pushed.
    """
    if isinstance(retval, PushResult):
        return retval.pushed
    return retval is True


def gitlabMergeRequestUrls(output):
    """Extracts GitLab merge request creation URLs from git push output.

    Args:
        output (str): Combined stdout and stderr from a git push.

    Returns:
        list: GitLab merge request creation URLs found after matching
            "create a merge request" remote messages.
    """
    urls = []
    expecting_url = False

    for line in output.splitlines():
        match = REMOTE_LINE_RE.match(line)
        if not match:
            continue

        body = match.group(1).strip()
        if CREATE_MERGE_REQUEST_RE.search(body):
            expecting_url = True
            continue

        if expecting_url:
            url_match = URL_RE.search(body)
            if url_match:
                urls.append(url_match.group(0))
                expecting_url = False
            elif body:
                expecting_url = False

    return urls


def remoteMessagesWithoutGitlabMergeRequestHints(output):
    """Filters remote messages while suppressing GitLab merge request hints.

    Args:
        output (str): Combined stdout and stderr from a git push.

    Returns:
        list: Remote message lines that should still be logged after removing
            GitLab merge request creation text and URL lines.
    """
    messages = []
    skipping_mr_url = False

    for line in output.splitlines():
        match = REMOTE_LINE_RE.match(line)
        if not match:
            continue

        body = match.group(1).strip()
        if CREATE_MERGE_REQUEST_RE.search(body):
            skipping_mr_url = True
            continue

        if skipping_mr_url:
            if not body:
                continue
            if URL_RE.search(body):
                skipping_mr_url = False
                continue
            skipping_mr_url = False

        if body:
            messages.append(line.strip())

    return messages


def uniqueItems(items):
    """Deduplicates a sequence while preserving first-seen order.

    Args:
        items (iterable): Values to deduplicate.

    Returns:
        list: Unique values in first-seen order.
    """
    unique = []
    seen = set()
    for item in items:
        if item not in seen:
            unique.append(item)
            seen.add(item)
    return unique


def logCollectedRemoteMessages(retvals):
    """Logs accumulated remote messages and a single grape review hint.

    Args:
        retvals (list): Return values from the multi-repo push launcher.
            PushResult values may contain captured git push output.
    """
    remote_messages = []
    merge_request_urls = []

    for retval in retvals:
        if not isinstance(retval, PushResult):
            continue
        remote_messages.extend(
            remoteMessagesWithoutGitlabMergeRequestHints(retval.output))
        merge_request_urls.extend(gitlabMergeRequestUrls(retval.output))

    for message in uniqueItems(remote_messages):
        logging.info(message)

    merge_request_urls = uniqueItems(merge_request_urls)
    if not merge_request_urls:
        return

    repo_count = len(merge_request_urls)
    repo_noun = "repo" if repo_count == 1 else "repos"
    logging.info(
        f"GitLab reported merge request creation links for {repo_count} pushed {repo_noun}.")
    logging.info(
        "Run grape review to create or update merge requests for this workspace:")
    logging.info("  grape review")


def push(repo='', branch='master', args=None, *, workspace_dir):
    """Pushes the given branch if appropriate based on args.

    Default: only push when local branch is ahead of origin/<branch>.
    If --pushAll is provided, always push (previous behavior).
    """
    if args is None:
        args = {}

    push_all = args.get("--pushAll", False) if isinstance(args, dict) else False
    quiet_remote_messages = args.get("--quietRemoteMessages", False) if isinstance(args, dict) else False
    accumulate_remote_messages = (
        args.get("_accumulateRemoteMessages", False) if isinstance(args, dict) else False)
    quiet_git_remote_messages = quiet_remote_messages or accumulate_remote_messages

    if push_all:
        logging.info(f"Pushing {branch} in {repo} (pushAll)...")
        output = git.push(f"-u origin {branch}", throwOnFail=True,
                          quietRemoteMessages=quiet_git_remote_messages,
                          execution_path=repo)
        return PushResult(True, repo, branch, output)

    # Determine if local is ahead of origin; if not, skip
    try:
        remote_ref = git.join_list_as_git_path(['remotes', 'origin', branch])
        branches_output = git.branch("-a", execution_path=repo).split("\n")
        remote_ref_exists = False
        for b in branches_output:
            b_clean = b.replace('*', '').strip()
            if b_clean == remote_ref:
                remote_ref_exists = True
                break

        if not remote_ref_exists:
            # No remote tracking branch present locally; push to create it
            logging.info(f"Pushing {branch} in {repo} (no remote ref exists)...")
            output = git.push(f"-u origin {branch}", throwOnFail=True,
                              quietRemoteMessages=quiet_git_remote_messages,
                              execution_path=repo)
            return PushResult(True, repo, branch, output)

        local_contains_remote = git.branchUpToDateWith(branch, remote_ref, execution_path=repo)
        remote_contains_local = git.branchUpToDateWith(remote_ref, branch, execution_path=repo)

        if local_contains_remote and not remote_contains_local:
            logging.info(f"Pushing {branch} in {repo} (local ahead of origin)...")
            output = git.push(f"-u origin {branch}", throwOnFail=True,
                              quietRemoteMessages=quiet_git_remote_messages,
                              execution_path=repo)
            return PushResult(True, repo, branch, output)
        else:
            if remote_contains_local and local_contains_remote:
                logging.debug(f"Skipping push for {repo} on {branch}: up to date with origin.")
            elif remote_contains_local and not local_contains_remote:
                logging.info(f"Skipping push for {repo} on {branch}: behind origin.")
            else:
                logging.info(f"Skipping push for {repo} on {branch}: divergent")
            return PushResult(False, repo, branch)
    except grape_errors.GrapeGitIndexLockError as e:
        e.LogError(f"determine push necessity in {repo}")
        raise e
    except grape_errors.GrapeGitError as e:
        logging.error("Failed to determine push necessity; attempting push anyway.")
        logging.debug(e.gitOutput)
        output = git.push(f"-u origin {branch}", throwOnFail=True,
                          quietRemoteMessages=quiet_git_remote_messages,
                          execution_path=repo)
        return PushResult(True, repo, branch, output)

def handlePushMRE(mre):
    for e1 in mre.exceptions():
        try:
            raise e1
        except grape_errors.GrapeGitIndexLockError as e:
            e.LogError("push branch")
            return False
        except grape_errors.GrapeGitError as e:
            logging.error("Failed to push branch.")
            logging.error(e.gitCommand)
            logging.error(e.cwd)
            logging.error(e.gitOutput)
            return False

if __name__ == "__main__":
    from vine import grapeMenu
    menu = grapeMenu.menu()
    menu.applyMenuChoice("push", [])
