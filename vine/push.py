import logging
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

    Usage: grape-push [--noTopLevel] [--noRecurse] [--noRecurseSubprojects] [--pushAll]

    Options:
        --noTopLevel            Don't perform push in top level repo.
        --noRecurse             Don't perform pushes in submodules.
        --noRecurseSubprojects  Don't perform pushes in nested subprojects.
        --pushAll               Push all repositories regardless of whether local is ahead of origin.

    """
    def __init__(self):
        super(Push, self).__init__()
        self._key = "push"
        self._section = "Workspace"

    def description(self):
        return "Pushes your current branch to origin in all projects in this workspace."

    @log_wrapper
    def execute(self, args):
        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
            push,
            skipSubmodules=args["--noRecurse"],
            runInSubprojects=not args["--noRecurseSubprojects"],
            runInOuter=not args["--noTopLevel"],
            workspace_dir=self.workspace_dir,
            globalArgs=args)
        retvals = launcher.launchFromWorkspaceDir(handleMRE=handlePushMRE)

        if True not in retvals:
            logging.info("No repositories were pushed to origin. Local repos are up to date.")
        else:
            logging.info("Pushed current branch to origin")
        return True

    def setDefaultConfig(self, config):
        pass

def push(repo='', branch='master', args={}, *, workspace_dir):
    """Pushes the given branch if appropriate based on args.

    Default: only push when local branch is ahead of origin/<branch>.
    If --pushAll is provided, always push (previous behavior).
    """
    push_all = args.get("--pushAll", False) if isinstance(args, dict) else False

    if push_all:
        logging.info(f"Pushing {branch} in {repo} (pushAll)...")
        git.push(f"-u origin {branch}", throwOnFail=True, execution_path=repo)
        return True

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
            git.push(f"-u origin {branch}", throwOnFail=True, execution_path=repo)
            return True

        local_contains_remote = git.branchUpToDateWith(branch, remote_ref, execution_path=repo)
        remote_contains_local = git.branchUpToDateWith(remote_ref, branch, execution_path=repo)

        if local_contains_remote and not remote_contains_local:
            logging.info(f"Pushing {branch} in {repo} (local ahead of origin)...")
            git.push(f"-u origin {branch}", throwOnFail=True, execution_path=repo)
            return True
        else:
            if remote_contains_local and local_contains_remote:
                logging.debug(f"Skipping push for {repo} on {branch}: up to date with origin.")
            elif remote_contains_local and not local_contains_remote:
                logging.info(f"Skipping push for {repo} on {branch}: behind origin.")
            else:
                logging.info(f"Skipping push for {repo} on {branch}: divergent")
            return False
    except grape_errors.GrapeGitIndexLockError as e:
        e.LogError(f"determine push necessity in {repo}")
        raise e
    except grape_errors.GrapeGitError as e:
        logging.error("Failed to determine push necessity; attempting push anyway.")
        logging.debug(e.gitOutput)
        git.push(f"-u origin {branch}", throwOnFail=True, execution_path=repo)
        return True

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
