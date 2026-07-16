import logging
import os
import shlex
import subprocess
import sys
from vine import config_parser_user
from vine import grape_errors
from vine import grapeGit as git
from vine import multi_repo_cmd_launcher
from vine import utility
from vine.option import Option
from vine.vine_logging import log_wrapper
from vine.workspace_dir_handler import WorkspaceDirHandler


class Diff(Option, WorkspaceDirHandler):
    """
    grape diff
    Print diffs across the outer workspace repo, active submodules, and active nested subprojects.

    Usage: grape-diff [--patch | --stat | --name-only | --name-status]
                      [--mergeDiff | --rawDiff]
                      [--noFetch]
                      [--noTopLevel] [--noSubmodules] [--noNestedSubprojects]
           grape-diff [--patch | --stat | --name-only | --name-status]
                      [--mergeDiff | --rawDiff]
                      [--noFetch]
                      [--noTopLevel] [--noSubmodules] [--noNestedSubprojects]
                      <ref1>
           grape-diff [--patch | --stat | --name-only | --name-status]
                      [--mergeDiff | --rawDiff]
                      [--noFetch]
                      [--noTopLevel] [--noSubmodules] [--noNestedSubprojects]
                      <ref1> <ref2>
           grape-diff [--patch | --stat | --name-only | --name-status]
                      [--mergeDiff | --rawDiff]
                      [--noFetch]
                      [--noTopLevel] [--noSubmodules] [--noNestedSubprojects]
                      -- <path>...
           grape-diff [--patch | --stat | --name-only | --name-status]
                      [--mergeDiff | --rawDiff]
                      [--noFetch]
                      [--noTopLevel] [--noSubmodules] [--noNestedSubprojects]
                      <ref1> -- <path>...
           grape-diff [--patch | --stat | --name-only | --name-status]
                      [--mergeDiff | --rawDiff]
                      [--noFetch]
                      [--noTopLevel] [--noSubmodules] [--noNestedSubprojects]
                      <ref1> <ref2> -- <path>...
           grape-diff [--patch | --stat | --name-only | --name-status]
                      --cached
                      [--noFetch]
                      [--noTopLevel] [--noSubmodules] [--noNestedSubprojects]
           grape-diff [--patch | --stat | --name-only | --name-status]
                      --cached
                      [--noFetch]
                      [--noTopLevel] [--noSubmodules] [--noNestedSubprojects]
                      <ref1>
           grape-diff [--patch | --stat | --name-only | --name-status]
                      --cached
                      [--noFetch]
                      [--noTopLevel] [--noSubmodules] [--noNestedSubprojects]
                      -- <path>...
           grape-diff [--patch | --stat | --name-only | --name-status]
                      --cached
                      [--noFetch]
                      [--noTopLevel] [--noSubmodules] [--noNestedSubprojects]
                      <ref1> -- <path>...

    Options:
        --patch                  Print the patch output. This is the default.
        --stat                   Print diffstat output instead of patches.
        --name-only              Print only changed file names.
        --name-status            Print changed file names with status letters.
        --cached                 Compare staged changes instead of worktree changes. Supports zero or one ref.
        --mergeDiff              With two refs, diff changes on <ref2> from the common ancestor (<ref1>...<ref2>).
        --rawDiff                With two refs, diff the exact branch tips (<ref1> <ref2>) (default).
        --noFetch                Do not fetch missing origin refs before diffing.
        --noTopLevel             Do not diff the outer level project.
        --noSubmodules           Do not diff active submodules.
        --noNestedSubprojects    Do not diff active nested subprojects.
        <ref1>                   Reference to compare against the worktree, or the left side of a two-ref diff.
        <ref2>                   Right side of a two-ref diff.
        <path>                   Path to diff, resolved relative to the current working directory after `--`.

    """
    def __init__(self):
        super(Diff, self).__init__()
        self._key = "diff"
        self._section = "Code Reviews"

    def description(self):
        """Summarize the command for menu display.

        Returns:
            str: A short human-readable description of the command.
        """
        return "Print diffs across this workspace"

    @log_wrapper
    def execute(self, args):
        """Run the workspace-aware diff command.

        Args:
            args (dict): Parsed command-line arguments from docopt.

        Returns:
            bool: True when the command completes, even if no diffs are found.
        """
        output_mode = _select_output_mode(args)
        if output_mode is None:
            logging.error("Choose at most one of --patch, --stat, --name-only, or --name-status.")
            return False

        diff_request = _determine_diff_request(args)
        _, _, raw_paths = _normalize_positional_args(args)
        path_filter_requested = bool(raw_paths)
        requested_paths = _resolve_requested_paths(
            args,
            workspace_dir=self.workspace_dir,
            current_dir=os.getcwd(),
        )
        launch_tuples = _build_launch_tuples(
            workspace_dir=self.workspace_dir,
            diff_request=diff_request,
            requested_paths=requested_paths,
            path_filter_requested=path_filter_requested,
            output_mode=output_mode,
            no_fetch=args["--noFetch"],
            include_outer=not args["--noTopLevel"],
            include_submodules=not args["--noSubmodules"],
            include_nested=not args["--noNestedSubprojects"],
        )
        if path_filter_requested and not launch_tuples:
            logging.info("No repositories matched the requested path filter.")
            return True

        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
            diff_repo,
            listOfRepoBranchArgTuples=launch_tuples,
            workspace_dir=self.workspace_dir,
        )
        results = launcher.launchFromWorkspaceDir(noPause=True)

        emitted_output = False
        had_successful_diff = False
        rendered_sections = []
        for result in results:
            warning = result.get("warning")
            if warning:
                logging.warning(warning)
                continue
            had_successful_diff = True
            output = result.get("output", "")
            if not output.strip():
                continue
            emitted_output = True
            rendered_sections.append(
                _format_diff_section(result["display_path"], result["spec"], output)
            )

        if not emitted_output and (had_successful_diff or not results):
            logging.info("No differences found.")
        elif not _page_output_if_tty("".join(rendered_sections), self.workspace_dir):
            logging.info("".join(rendered_sections))
        return True

    def setDefaultConfig(self, config):
        """Populate default config values for this command.

        Args:
            config (ConfigParser): The mutable GRAPE configuration object.
        """
        pass


def diff_repo(repo="", branch="", args=None, *, workspace_dir):
    """Render a diff for a single repository in the workspace.

    Args:
        repo (str): Absolute path to the repository to diff.
        branch (str): Left-side ref for the diff in this repository when applicable.
        args (dict | None): Per-repository diff configuration supplied by the launcher.
        workspace_dir (str): Absolute path to the workspace root.

    Returns:
        dict: A result payload containing the rendered diff output or a warning.
    """
    if args is None:
        args = {}

    display_path = args["display_path"]
    repo_type = args["repo_type"]
    target_ref = args["target_ref"]
    diff_type = args["diff_type"]
    output_mode = args["output_mode"]
    do_merge_diff = args["do_merge_diff"]
    no_fetch = args["no_fetch"]
    pathspecs = args["pathspecs"]

    try:
        resolved_base = utility.resolve_repo_ref(branch, repo_type, no_fetch, repo)
        resolved_target = utility.resolve_repo_ref(target_ref, repo_type, no_fetch, repo)
        diff_spec, display_spec = _render_diff_spec(
            resolved_base, resolved_target, diff_type, do_merge_diff
        )
        diff_args = _render_git_diff_args(output_mode, diff_spec, display_path, pathspecs)
        output = git.diff(diff_args, execution_path=repo)
        return {
            "display_path": display_path,
            "spec": _render_display_spec(display_spec, pathspecs),
            "output": output,
        }
    except (FileNotFoundError, grape_errors.GrapeGitError) as exc:
        return {
            "display_path": display_path,
            "spec": _render_display_spec(
                _render_diff_spec(branch, target_ref, diff_type, do_merge_diff)[1],
                pathspecs,
            ),
            "warning": _format_diff_warning(display_path, branch, target_ref, diff_type, exc),
            "output": "",
        }


def _select_output_mode(args):
    """Choose the requested diff output mode.

    Args:
        args (dict): Parsed command-line arguments from docopt.

    Returns:
        str | None: The selected mode, or None when the selection is invalid.
    """
    selected_modes = [
        mode for flag, mode in (
            ("--patch", "patch"),
            ("--stat", "stat"),
            ("--name-only", "name-only"),
            ("--name-status", "name-status"),
        )
        if args[flag]
    ]
    if len(selected_modes) > 1:
        return None
    if selected_modes:
        return selected_modes[0]
    return "patch"


def _determine_diff_request(args):
    """Resolve the requested diff shape from the provided command-line arguments.

    Args:
        args (dict): Parsed command-line arguments from docopt.

    Returns:
        dict: The requested diff form and any supplied refs.
    """
    ref1, ref2, _ = _normalize_positional_args(args)
    is_cached = args["--cached"]

    if ref1 and ref2:
        return {
            "diff_type": "two_ref",
            "base_ref": ref1,
            "target_ref": ref2,
            "do_merge_diff": args["--mergeDiff"],
        }
    if ref1:
        return {
            "diff_type": "cached_ref" if is_cached else "worktree_ref",
            "base_ref": ref1,
            "target_ref": None,
            "do_merge_diff": False,
        }
    return {
        "diff_type": "cached" if is_cached else "worktree",
        "base_ref": None,
        "target_ref": None,
        "do_merge_diff": False,
    }


def _normalize_positional_args(args):
    """Normalize docopt positional output into refs plus path arguments.

    Args:
        args (dict): Parsed command-line arguments from docopt.

    Returns:
        tuple[str | None, str | None, list[str]]: Normalized ref1, ref2, and raw path arguments.
    """
    ref1 = args["<ref1>"]
    ref2 = args["<ref2>"]
    raw_paths = list(args.get("<path>") or [])

    if ref1 == "--":
        if ref2:
            raw_paths.insert(0, ref2)
        return None, None, raw_paths
    if ref2 == "--":
        return ref1, None, raw_paths
    return ref1, ref2, raw_paths


def _resolve_requested_paths(args, *, workspace_dir, current_dir):
    """Resolve CLI path arguments into workspace-local absolute paths.

    Args:
        args (dict): Parsed command-line arguments from docopt.
        workspace_dir (str): Absolute path to the workspace root.
        current_dir (str): Absolute path to the user's current working directory.

    Returns:
        list[str]: Absolute normalized paths that fall within the workspace.
    """
    requested_paths = []
    workspace_root = os.path.realpath(workspace_dir)
    current_root = os.path.realpath(current_dir)

    _, _, raw_paths = _normalize_positional_args(args)
    for raw_path in raw_paths:
        candidate_path = raw_path if os.path.isabs(raw_path) else os.path.join(current_root, raw_path)
        absolute_path = os.path.realpath(candidate_path)
        if not utility.is_same_path_or_child(absolute_path, workspace_root):
            logging.warning("Ignoring path outside workspace: `%s`", raw_path)
            continue
        requested_paths.append(absolute_path)
    return requested_paths


def _build_launch_tuples(*, workspace_dir, diff_request, requested_paths, path_filter_requested,
                         output_mode,
                         no_fetch, include_outer,
                         include_submodules, include_nested):
    """Build per-repository work items for the multi-repo launcher.

    Args:
        workspace_dir (str): Absolute path to the workspace root.
        diff_request (dict): Requested diff form and workspace-level refs.
        requested_paths (list[str]): Absolute paths requested after the `--` separator.
        path_filter_requested (bool): Whether the CLI included a `-- <path>` filter.
        output_mode (str): Selected diff rendering mode.
        no_fetch (bool): Whether origin refs should avoid fetches.
        include_outer (bool): Whether to include the outer repository.
        include_submodules (bool): Whether to include active submodules.
        include_nested (bool): Whether to include active nested subprojects.

    Returns:
        list[tuple[str, str, dict]]: Launcher tuples of repo path, base ref, and per-repo args.
    """
    base_ref = diff_request["base_ref"]
    target_ref = diff_request["target_ref"]
    diff_type = diff_request["diff_type"]
    do_merge_diff = diff_request["do_merge_diff"]
    if path_filter_requested and not requested_paths:
        return []
    repo_entries = []
    if include_outer:
        repo_entries.append(("",
                             {
                                 "display_path": "workspace",
                                 "repo_type": "outer",
                             }))

    if include_nested:
        for nested in config_parser_user.getAllActiveNestedSubprojectPrefixes(workspaceDir=workspace_dir):
            repo_entries.append((nested,
                                 {
                                     "display_path": nested,
                                     "repo_type": "nested",
                                 }))

    if include_submodules:
        for submodule in git.getActiveSubmodules(execution_path=workspace_dir):
            repo_entries.append((submodule,
                                 {
                                     "display_path": submodule,
                                     "repo_type": "submodule",
                                 }))

    repo_paths = [
        os.path.realpath(os.path.join(workspace_dir, repo_rel)) if repo_rel else os.path.realpath(workspace_dir)
        for repo_rel, _ in repo_entries
    ]
    launch_tuples = []
    for (repo_rel, repo_args), repo_path in zip(repo_entries, repo_paths):
        pathspecs = utility.select_repo_pathspecs(requested_paths, repo_path, repo_paths)
        if requested_paths and not pathspecs:
            continue
        launch_tuples.append((
            repo_rel,
            base_ref,
            {
                "display_path": repo_args["display_path"],
                "repo_type": repo_args["repo_type"],
                "diff_type": diff_type,
                "target_ref": target_ref,
                "output_mode": output_mode,
                "do_merge_diff": do_merge_diff,
                "no_fetch": no_fetch,
                "pathspecs": pathspecs,
            },
        ))
    return launch_tuples


def _render_diff_spec(base_ref, target_ref, diff_type, do_merge_diff):
    """Format the git diff refspec for the selected diff mode.

    Args:
        base_ref (str | None): Base ref in repository-local terms.
        target_ref (str | None): Target ref in repository-local terms.
        diff_type (str): Requested diff form.
        do_merge_diff (bool): Whether to use merge-base (`...`) semantics.

    Returns:
        tuple[str, str]: A git-compatible diff refspec and a display label.
    """
    if diff_type == "worktree":
        return "", "<worktree>"
    if diff_type == "cached":
        return "--cached", "--cached"
    if diff_type == "worktree_ref":
        return base_ref, base_ref
    if diff_type == "cached_ref":
        return f"--cached {base_ref}", f"--cached {base_ref}"
    if do_merge_diff:
        return f"{base_ref}...{target_ref}", f"{base_ref}...{target_ref}"
    return f"{base_ref} {target_ref}", f"{base_ref} {target_ref}"


def _render_git_diff_args(output_mode, diff_spec, display_path, pathspecs):
    """Construct the argument string passed to `git diff`.

    Args:
        output_mode (str): Selected diff rendering mode.
        diff_spec (str): Git diff refspec to compare.
        display_path (str): Repo label used when formatting patch prefixes.
        pathspecs (list[str]): Repository-local pathspecs appended after `--`.

    Returns:
        str: Argument string for `git diff`.
    """
    mode_args = {
        "patch": "",
        "stat": "--stat",
        "name-only": "--name-only",
        "name-status": "--name-status",
    }[output_mode]

    if output_mode == "patch":
        repo_prefix = "workspace" if display_path == "workspace" else display_path
        prefix_args = f'--src-prefix="a/{repo_prefix}/" --dst-prefix="b/{repo_prefix}/" '
    else:
        prefix_args = ""

    rendered_args = f"{mode_args} {prefix_args}{diff_spec}".strip()
    if pathspecs:
        rendered_paths = " ".join(shlex.quote(pathspec) for pathspec in pathspecs)
        rendered_args = f"{rendered_args} -- {rendered_paths}".strip()
    return rendered_args


def _render_display_spec(diff_spec, pathspecs):
    """Render the user-facing diff label for one repository section.

    Args:
        diff_spec (str): Displayable refspec for the diff.
        pathspecs (list[str]): Repository-local pathspecs appended after `--`.

    Returns:
        str: User-facing diff label.
    """
    if not pathspecs:
        return diff_spec
    rendered_paths = " ".join(shlex.quote(pathspec) for pathspec in pathspecs)
    return f"{diff_spec} -- {rendered_paths}"


def _format_diff_section(display_path, spec, output):
    """Render one repository's diff section for aggregate output.

    Args:
        display_path (str): Human-readable repository label.
        spec (str): Refspec used for the diff.
        output (str): Raw diff output for the repository.

    Returns:
        str: The formatted diff section.
    """
    return f"[{display_path}] {spec}\n{output.rstrip()}\n"


def _format_diff_warning(display_path, base_ref, target_ref, diff_type, exc):
    """Create a concise user-facing warning for a failed repository diff.

    Args:
        display_path (str): Human-readable repository label.
        base_ref (str | None): Base ref requested for the diff.
        target_ref (str | None): Target ref requested for the diff.
        diff_type (str): Requested diff form.
        exc (Exception): The underlying failure raised while preparing the diff.

    Returns:
        str: A concise warning message suitable for logging.
    """
    if isinstance(exc, FileNotFoundError):
        return f"Skipping [{display_path}]: repository path is unavailable."

    git_output = exc.gitOutput.strip() if getattr(exc, "gitOutput", None) else str(exc)
    if "unknown revision or path not in the working tree" in git_output.lower() or "bad revision" in git_output.lower():
        if diff_type == "worktree":
            return f"Skipping [{display_path}]: could not compute worktree diff."
        if diff_type == "worktree_ref":
            return f"Skipping [{display_path}]: could not resolve ref `{base_ref}`."
        return f"Skipping [{display_path}]: could not resolve refs for `{base_ref}` vs `{target_ref}`."
    return f"Skipping [{display_path}]: {git_output}"


def _page_output_if_tty(output, workspace_dir):
    """Send diff output through Git's pager for interactive terminals.

    Args:
        output (str): Aggregated diff output to display.
        workspace_dir (str): Absolute path to the workspace root.

    Returns:
        bool: True when the pager handled the output successfully.
    """
    stdout = sys.stdout
    if not hasattr(stdout, "isatty") or not stdout.isatty():
        return False

    pager = _resolve_git_pager(workspace_dir)
    if not pager:
        return False

    try:
        completed_process = subprocess.run(
            pager,
            input=output.encode(),
            cwd=workspace_dir,
            shell=True,
            check=False,
        )
    except OSError:
        return False
    return completed_process.returncode == 0


def _resolve_git_pager(workspace_dir):
    """Resolve the pager command Git would use in this workspace.

    Args:
        workspace_dir (str): Absolute path to the workspace root.

    Returns:
        str: The resolved pager command, or an empty string when unavailable.
    """
    try:
        pager = git.gitcmd(
            "var GIT_PAGER",
            "could not determine git pager",
            execution_path=workspace_dir,
        ).strip()
    except grape_errors.GrapeGitError:
        return ""
    return pager
