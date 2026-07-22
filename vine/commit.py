import logging
import os
import shlex
from vine import config_parser_user
from vine import grape_errors
from vine import grapeGit as git
from vine import multi_repo_cmd_launcher
from vine import utility
from vine.option import Option
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.vine_logging import log_wrapper


class Commit(Option, WorkspaceDirHandler):
    """
    Usage: grape-commit [-m <message>] [--failIfNoCommit] [-a | <filetree>...]

    Options:
        -m <message>      The commit message.
        -a                Commit modified files that have not been staged.
        --failIfNoCommit  Exit with failure if no files were committed.


    Arguments:
        <filetree>... Files or directories to include, resolved relative to the current working directory.

    """
    def __init__(self):
        super(Commit, self).__init__()
        self._key = "commit"
        self._section = "Workspace"

    def description(self):
        """Summarize the command for menu display.

        Returns:
            str: A short human-readable description of the command.
        """
        return "runs git commit in all projects in this workspace"

    @log_wrapper
    def execute(self, args):
        """Commit changes across the workspace in child repos first, then outer.

        Args:
            args (dict): Parsed command-line arguments from docopt.

        Returns:
            bool: True when the command succeeds, or when empty commits are
            allowed and no repositories had matching changes.
        """
        commitargs = ""
        requested_paths = []
        if args['-a']:
            commitargs = commitargs +  " -a"
        elif args["<filetree>"]:
            requested_paths = utility.resolve_workspace_paths(
                args["<filetree>"],
                workspace_dir=self.workspace_dir,
                current_dir=os.getcwd(),
            )
            if not requested_paths:
                logging.info("No repositories matched the requested file selection.")
                return not args['--failIfNoCommit']
        if not args['-m']:
            args["-m"] = utility.userInput("Please enter commit message:")

        filesCommitted = False
        commitargs += _render_commit_message_arg(args["-m"])

        if requested_paths:
            # Scoped commits reuse the same two-phase ordering, but only for the
            # repositories and pathspecs selected by the requested fileish paths.
            filesCommitted = self._commit_requested_paths(commitargs, requested_paths)
            if args['--failIfNoCommit']:
                return filesCommitted
            else:
                return True

        # Unscoped commits first let child repositories record their own history.
        # Any resulting submodule gitlink updates are then staged in the outer
        # repository before the final top-level commit is attempted.
        filesCommitted, committed_submodules = self._launch_child_commits(
            commitargs,
            requested_paths=None,
        )
        _stage_submodule_gitlinks(committed_submodules, self.workspace_dir)

        if git.status("--porcelain", execution_path=self.workspace_dir):
            # The top-level commit runs after child repositories so that nested
            # project metadata and submodule gitlinks are captured in one outer
            # commit, matching GRAPE's existing ordering semantics.
            commit_result = commit_repo(
                repo=self.workspace_dir,
                branch="",
                args={
                    "commitargs": commitargs,
                    "display_path": "workspace",
                    "pathspecs": [],
                    "has_changes": True,
                },
                workspace_dir=self.workspace_dir,
            )
            if commit_result["committed"]:
                filesCommitted = True

        if args['--failIfNoCommit']:
            return filesCommitted
        else:
            return True

    def setDefaultConfig(self,config):
        """Populate default config values for this command.

        Args:
            config (ConfigParser): The mutable GRAPE configuration object.
        """
        pass

    def _commit_requested_paths(self, commitargs, requested_paths):
        """Commit only the repositories touched by explicit fileish arguments.

        Args:
            commitargs (str): Rendered git commit arguments such as `-m`.
            requested_paths (list[str]): Absolute workspace-local paths selected
                by the user.

        Returns:
            bool: True when at least one repository committed matching changes.
        """
        repo_entries = _build_repo_entries(self.workspace_dir)
        repo_paths = [repo_path for _, repo_path in repo_entries]
        repo_pathspecs = {
            repo_path: utility.select_repo_pathspecs(requested_paths, repo_path, repo_paths)
            for repo_path in repo_paths
        }
        repo_pathspecs = {
            repo_path: pathspecs for repo_path, pathspecs in repo_pathspecs.items() if pathspecs
        }
        workspace_pathspecs = list(repo_pathspecs.get(os.path.realpath(self.workspace_dir), []))

        # Launch child repository commits first so submodule gitlink changes can
        # be staged back into the outer repository before the outer commit runs.
        files_committed, committed_submodules = self._launch_child_commits(
            commitargs,
            requested_paths=repo_pathspecs,
        )
        _stage_submodule_gitlinks(committed_submodules, self.workspace_dir)

        # A scoped ancestor path can imply both a child repo commit and the
        # corresponding outer-repo gitlink update, so append successful
        # submodule paths to the outer pathspec list before checking the outer
        # repository for matching changes.
        for sub in committed_submodules:
            if sub not in workspace_pathspecs:
                workspace_pathspecs.append(sub)

        if workspace_pathspecs and _repo_has_selected_changes(self.workspace_dir, workspace_pathspecs):
            commit_result = commit_repo(
                repo=self.workspace_dir,
                branch="",
                args={
                    "commitargs": commitargs,
                    "display_path": "workspace",
                    "pathspecs": workspace_pathspecs,
                    "has_changes": True,
                },
                workspace_dir=self.workspace_dir,
            )
            if commit_result["committed"]:
                files_committed = True

        return files_committed

    def _launch_child_commits(self, commitargs, requested_paths):
        """Run commit operations for nested repos and submodules via launcher.

        Args:
            commitargs (str): Rendered git commit arguments such as `-m`.
            requested_paths (dict[str, list[str]] | None): Optional mapping from
                absolute repo paths to repo-local pathspecs for scoped commits.
                When `None`, child repositories run as unscoped commits.

        Returns:
            tuple[bool, list[str]]: Whether any child repository committed, and
            the list of submodule relative paths whose gitlinks must be staged in
            the outer repository.
        """
        launch_tuples = _build_child_commit_launch_tuples(
            workspace_dir=self.workspace_dir,
            commitargs=commitargs,
            requested_paths=requested_paths,
        )
        if not launch_tuples:
            return False, []

        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
            commit_repo,
            listOfRepoBranchArgTuples=launch_tuples,
            workspace_dir=self.workspace_dir,
        )
        results = launcher.launchFromWorkspaceDir(noPause=True)

        # Collect launcher results into the two facts the outer phase needs:
        # whether anything committed at all, and which submodule gitlinks now
        # require staging in the top-level repository.
        files_committed = False
        committed_submodules = []
        for result in results:
            if result["committed"]:
                files_committed = True
                if result["stage_after_commit"]:
                    committed_submodules.append(result["repo_rel"])
        return files_committed, committed_submodules


def _build_repo_entries(workspace_dir):
    """List workspace repositories in top-level, nested, and submodule form.

    Args:
        workspace_dir (str): Absolute path to the workspace root.

    Returns:
        list[tuple[str, str]]: Relative repo labels paired with absolute repo
        paths.
    """
    repo_entries = [
        ("", os.path.realpath(workspace_dir)),
    ]
    for nested in config_parser_user.getAllActiveNestedSubprojectPrefixes(workspaceDir=workspace_dir):
        repo_entries.append((nested, os.path.realpath(os.path.join(workspace_dir, nested))))
    for submodule in git.getActiveSubmodules(execution_path=workspace_dir):
        repo_entries.append((submodule, os.path.realpath(os.path.join(workspace_dir, submodule))))
    return repo_entries


def _build_child_commit_launch_tuples(*, workspace_dir, commitargs, requested_paths):
    """Build launcher work items for nested projects and submodules.

    Args:
        workspace_dir (str): Absolute path to the workspace root.
        commitargs (str): Rendered git commit arguments such as `-m`.
        requested_paths (dict[str, list[str]] | None): Optional mapping from
            absolute repo paths to repo-local pathspecs for scoped commits.

    Returns:
        list[tuple[str, str, dict]]: Launcher tuples describing child repo
        commit tasks.
    """
    launch_tuples = []

    # Nested subprojects commit independently but do not require any follow-up
    # staging in the outer repo because they are ignored by the outer Git repo.
    for nested in config_parser_user.getAllActiveNestedSubprojectPrefixes(workspaceDir=workspace_dir):
        repo_path = os.path.realpath(os.path.join(workspace_dir, nested))
        pathspecs = _resolve_repo_pathspecs(requested_paths, repo_path)
        if pathspecs is None:
            continue
        launch_tuples.append((
            nested,
            "",
            {
                "commitargs": commitargs,
                "display_path": nested,
                "pathspecs": pathspecs,
                "repo_rel": nested,
                "stage_after_commit": False,
            },
        ))

    # Submodule commits must report back so the caller can stage the resulting
    # gitlink updates in the outer repository before the top-level commit.
    for submodule in git.getActiveSubmodules(execution_path=workspace_dir):
        repo_path = os.path.realpath(os.path.join(workspace_dir, submodule))
        pathspecs = _resolve_repo_pathspecs(requested_paths, repo_path)
        if pathspecs is None:
            continue
        launch_tuples.append((
            submodule,
            "",
            {
                "commitargs": commitargs,
                "display_path": submodule,
                "pathspecs": pathspecs,
                "repo_rel": submodule,
                "stage_after_commit": True,
            },
        ))

    return launch_tuples


def _resolve_repo_pathspecs(requested_paths, repo_path):
    """Return scoped pathspecs for one repo or `None` when it is excluded.

    Args:
        requested_paths (dict[str, list[str]] | None): Optional mapping from
            absolute repo paths to repo-local pathspecs.
        repo_path (str): Absolute path to the repository being considered.

    Returns:
        list[str] | None: Repo-local pathspecs, an empty list for unscoped
        commits, or `None` when the repo is outside the requested scope.
    """
    if requested_paths is None:
        return []
    pathspecs = requested_paths.get(repo_path, [])
    if not pathspecs:
        return None
    return pathspecs


def _stage_submodule_gitlinks(submodules, workspace_dir):
    """Stage outer-repo gitlink updates for committed submodules.

    Args:
        submodules (list[str]): Workspace-relative submodule paths to stage.
        workspace_dir (str): Absolute path to the workspace root.
    """
    for submodule in submodules:
        logging.info(f"Staging committed change in {submodule}...")
        git.add(_render_pathspecs([submodule]), execution_path=workspace_dir)


def commit_repo(repo="", branch="", args=None, *, workspace_dir):
    """Commit one repository for launcher-driven commit phases.

    Args:
        repo (str): Absolute path to the repository being committed.
        branch (str): Unused launcher branch slot; accepted for launcher
            compatibility.
        args (dict | None): Per-repository commit configuration.
        workspace_dir (str): Absolute path to the workspace root. Unused by the
            implementation but required by the launcher callback contract.

    Returns:
        dict: Result payload describing whether the repo committed and whether a
        submodule gitlink should be staged afterward.
    """
    if args is None:
        args = {}

    pathspecs = args.get("pathspecs", [])
    display_path = args.get("display_path", repo or "workspace")
    rendered_pathspecs = _render_pathspecs(pathspecs)
    commitargs = args["commitargs"]
    has_changes = args.get("has_changes")

    if pathspecs:
        # Scoped commits only proceed when the selected repo-local pathspecs have
        # status entries. This prevents falling back to a whole-repo commit when
        # a requested ancestor path maps only to some other repository.
        if has_changes is None:
            has_changes = _repo_has_selected_changes(repo, pathspecs)
        if not has_changes:
            return {
                "committed": False,
                "repo_rel": args["repo_rel"],
                "stage_after_commit": args.get("stage_after_commit", False),
            }
        logging.info(f"Committing {_display_pathspecs(pathspecs)} in {display_path}...")
        commitargstr = f"{commitargs} {rendered_pathspecs}"
    else:
        # Unscoped child repo commits ignore untracked files to preserve the
        # historical `-uno` behavior, while outer commits can inject a pre-known
        # `has_changes=True` to include fully staged top-level additions.
        if has_changes is None:
            has_changes = bool(git.status("--porcelain -uno", execution_path=repo))
        if not has_changes:
            return {
                "committed": False,
                "repo_rel": args.get("repo_rel", ""),
                "stage_after_commit": args.get("stage_after_commit", False),
            }
        logging.info(f"Committing in {display_path}...")
        commitargstr = commitargs

    try:
        git.commit(commitargstr, execution_path=repo)
        return {
            "committed": True,
            "repo_rel": args.get("repo_rel", ""),
            "stage_after_commit": args.get("stage_after_commit", False),
        }
    except grape_errors.GrapeGitError:
        logging.error(f"Commit in {repo} failed. Perhaps there were no staged changes? Use -a to commit all modified files.")
        return {
            "committed": False,
            "repo_rel": args.get("repo_rel", ""),
            "stage_after_commit": args.get("stage_after_commit", False),
        }


def _render_pathspecs(pathspecs):
    """Render repo-local pathspecs for shell-safe git invocation.

    Args:
        pathspecs (list[str]): Repo-local git pathspecs.

    Returns:
        str: A shell-escaped space-delimited pathspec string.
    """
    return " ".join(shlex.quote(pathspec) for pathspec in pathspecs)


def _display_pathspecs(pathspecs):
    """Render pathspecs for human-readable logging.

    Args:
        pathspecs (list[str]): Repo-local git pathspecs.

    Returns:
        str: Space-delimited pathspecs for log messages.
    """
    return " ".join(pathspecs)


def _repo_has_selected_changes(repo_path, pathspecs):
    """Check whether a repository has status entries for selected pathspecs.

    Args:
        repo_path (str): Absolute path to the repository to inspect.
        pathspecs (list[str]): Repo-local git pathspecs to query.

    Returns:
        bool: True when the repo has matching staged or unstaged changes.
    """
    return bool(git.status(f"--porcelain -- {_render_pathspecs(pathspecs)}", execution_path=repo_path).strip())


def _normalize_commit_message(message):
    """Strip one layer of matching CLI quotes from a commit message.

    Args:
        message (str): Raw commit message from parsed CLI arguments.

    Returns:
        str: The normalized commit message.
    """
    if len(message) >= 2 and message[0] == message[-1] and message[0] in ("'", '"'):
        return message[1:-1]
    return message


def _render_commit_message_arg(message):
    """Render the commit message argument for GRAPE's shell-based git wrapper.

    Args:
        message (str): Raw commit message from parsed CLI arguments.

    Returns:
        str: A `-m` argument with one quote layer normalized and shell-safe
        double-quote escaping applied.
    """
    normalized = _normalize_commit_message(message).strip()
    escaped = normalized.replace("\\", "\\\\").replace('"', '\\"')
    return f' -m "{escaped}"'
