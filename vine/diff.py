import logging
from vine import config_parser_global
from vine import config_parser_user
from vine import grape_errors
from vine import grapeGit as git
from vine import multi_repo_cmd_launcher
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
                      [<ref1>] [<ref2>]

    Options:
        --patch                  Print the patch output. This is the default.
        --stat                   Print diffstat output instead of patches.
        --name-only              Print only changed file names.
        --name-status            Print changed file names with status letters.
        --mergeDiff              Diff changes on <ref2> from the common ancestor (<ref1>...<ref2>) (default).
        --rawDiff                Diff the exact branch tips (<ref1> <ref2>).
        --noFetch                Do not fetch missing origin refs before diffing.
        --noTopLevel             Do not diff the outer level project.
        --noSubmodules           Do not diff active submodules.
        --noNestedSubprojects    Do not diff active nested subprojects.
        <ref1>                   Base branch or reference. With one ref, defaults target to the current workspace branch.
        <ref2>                   Target branch or reference. With no refs, defaults to the current branch and its public branch.

    """
    def __init__(self):
        super(Diff, self).__init__()
        self._key = "diff"
        self._section = "Code Reviews"

    def description(self):
        return "Print diffs across this workspace"

    @log_wrapper
    def execute(self, args):
        output_mode = _select_output_mode(args)
        if output_mode is None:
            logging.error("Choose at most one of --patch, --stat, --name-only, or --name-status.")
            return False

        base_ref, target_ref = _determine_workspace_refs(args, self.workspace_dir)
        launch_tuples = _build_launch_tuples(
            workspace_dir=self.workspace_dir,
            base_ref=base_ref,
            target_ref=target_ref,
            output_mode=output_mode,
            do_merge_diff=not args["--rawDiff"],
            no_fetch=args["--noFetch"],
            include_outer=not args["--noTopLevel"],
            include_submodules=not args["--noSubmodules"],
            include_nested=not args["--noNestedSubprojects"],
        )

        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
            diff_repo,
            listOfRepoBranchArgTuples=launch_tuples,
            workspace_dir=self.workspace_dir,
        )
        results = launcher.launchFromWorkspaceDir(noPause=True)

        emitted_output = False
        for result in results:
            warning = result.get("warning")
            if warning:
                logging.warning(warning)
                continue
            output = result.get("output", "")
            if not output.strip():
                continue
            emitted_output = True
            logging.info(_format_diff_section(result["display_path"], result["spec"], output))

        if not emitted_output:
            logging.info("No differences found.")
        return True

    def setDefaultConfig(self, config):
        pass


def diff_repo(repo="", branch="", args=None, *, workspace_dir):
    if args is None:
        args = {}

    display_path = args["display_path"]
    repo_type = args["repo_type"]
    target_ref = args["target_ref"]
    output_mode = args["output_mode"]
    do_merge_diff = args["do_merge_diff"]
    no_fetch = args["no_fetch"]

    try:
        resolved_base = _resolve_repo_ref(branch, repo_type, no_fetch, repo)
        resolved_target = _resolve_repo_ref(target_ref, repo_type, no_fetch, repo)
        diff_spec = _render_diff_spec(resolved_base, resolved_target, do_merge_diff)
        diff_args = _render_git_diff_args(output_mode, diff_spec, display_path)
        output = git.diff(diff_args, execution_path=repo)
        return {"display_path": display_path, "spec": diff_spec, "output": output}
    except (FileNotFoundError, grape_errors.GrapeGitError) as exc:
        return {
            "display_path": display_path,
            "spec": _render_diff_spec(branch, target_ref, do_merge_diff),
            "warning": _format_diff_warning(display_path, branch, target_ref, exc),
            "output": "",
        }


def _select_output_mode(args):
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


def _determine_workspace_refs(args, workspace_dir):
    config = config_parser_global.grapeConfig()
    current_branch = git.currentBranch(execution_path=workspace_dir)
    ref1 = args["<ref1>"]
    ref2 = args["<ref2>"]

    if ref1 and ref2:
        return ref1, ref2
    if ref1:
        return ref1, current_branch
    return config.getPublicBranchFor(current_branch), current_branch


def _build_launch_tuples(*, workspace_dir, base_ref, target_ref, output_mode,
                         do_merge_diff, no_fetch, include_outer,
                         include_submodules, include_nested):
    launch_tuples = []
    if include_outer:
        launch_tuples.append((
            "",
            base_ref,
            {
                "display_path": "workspace",
                "repo_type": "outer",
                "target_ref": target_ref,
                "output_mode": output_mode,
                "do_merge_diff": do_merge_diff,
                "no_fetch": no_fetch,
            },
        ))

    if include_nested:
        for nested in config_parser_user.getAllActiveNestedSubprojectPrefixes(workspaceDir=workspace_dir):
            launch_tuples.append((
                nested,
                base_ref,
                {
                    "display_path": nested,
                    "repo_type": "nested",
                    "target_ref": target_ref,
                    "output_mode": output_mode,
                    "do_merge_diff": do_merge_diff,
                    "no_fetch": no_fetch,
                },
            ))

    if include_submodules:
        for submodule in git.getActiveSubmodules(execution_path=workspace_dir):
            launch_tuples.append((
                submodule,
                base_ref,
                {
                    "display_path": submodule,
                    "repo_type": "submodule",
                    "target_ref": target_ref,
                    "output_mode": output_mode,
                    "do_merge_diff": do_merge_diff,
                    "no_fetch": no_fetch,
                },
            ))
    return launch_tuples


def _resolve_repo_ref(ref, repo_type, no_fetch, repo):
    mapped_ref = _map_ref_for_repo(ref, repo_type)
    if mapped_ref.startswith("--"):
        return mapped_ref

    resolved_ref = mapped_ref
    try:
        git.shortSHA(resolved_ref, execution_path=repo)
    except grape_errors.GrapeGitError:
        if not resolved_ref.startswith("origin/"):
            resolved_ref = git.join_list_as_git_path(["origin", resolved_ref])

    if not no_fetch and resolved_ref.startswith("origin/"):
        try:
            git.fetch("origin", resolved_ref.partition("/")[2], execution_path=repo)
        except grape_errors.GrapeGitError:
            # Let the later diff attempt surface a concise warning if the ref still cannot be used.
            pass

    return resolved_ref


def _map_ref_for_repo(ref, repo_type):
    if repo_type != "submodule":
        return ref

    config = config_parser_global.grapeConfig()
    submodule_public_map = config.getMapping(Option.SECTION_WORKSPACE, "submodulepublicmappings")

    prefix = ""
    branch_name = ref
    if ref.startswith("origin/"):
        prefix = "origin/"
        branch_name = ref.partition("/")[2]

    public_branches = config.getPublicBranchList()
    if branch_name in public_branches:
        branch_name = submodule_public_map[branch_name]
        return prefix + branch_name

    return ref


def _render_diff_spec(base_ref, target_ref, do_merge_diff):
    if do_merge_diff:
        return f"{base_ref}...{target_ref}"
    return f"{base_ref} {target_ref}"


def _render_git_diff_args(output_mode, diff_spec, display_path):
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

    return f"{mode_args} {prefix_args}{diff_spec}".strip()


def _format_diff_section(display_path, spec, output):
    return f"[{display_path}] {spec}\n{output.rstrip()}\n"


def _format_diff_warning(display_path, base_ref, target_ref, exc):
    if isinstance(exc, FileNotFoundError):
        return f"Skipping [{display_path}]: repository path is unavailable."

    git_output = exc.gitOutput.strip() if getattr(exc, "gitOutput", None) else str(exc)
    if "unknown revision or path not in the working tree" in git_output.lower() or "bad revision" in git_output.lower():
        return f"Skipping [{display_path}]: could not resolve refs for `{base_ref}` vs `{target_ref}`."
    return f"Skipping [{display_path}]: {git_output}"
