"""Local and remote status reporting for branch stacks."""

import logging

from vine import grape_errors
from vine import grapeGit as git
from vine.stack import IntegrationTargetResolver


class StackStatus:
    """Inspect recorded stack branches without mutating their history."""

    def __init__(self, workspace_dir, manifest, repositories):
        self.workspace_dir = workspace_dir
        self.manifest = manifest
        self.repositories = {repo.key: repo for repo in repositories}

    @staticmethod
    def _counts(repo_path, left, right):
        output = git.gitcmd(
            f"rev-list --left-right --count {left}...{right}",
            "Could not compare stack branches", execution_path=repo_path)
        behind, ahead = output.split()
        return int(behind), int(ahead)

    @staticmethod
    def _remote_state(repo_path, branch, remote_tip):
        try:
            observed = git.SHA(
                f"refs/remotes/origin/{branch}", execution_path=repo_path)
        except grape_errors.GrapeGitError:
            return "unpushed", remote_tip is None
        if remote_tip is not None and observed != remote_tip:
            return "remote moved", False
        local_tip = git.SHA(branch, execution_path=repo_path)
        if local_tip == observed:
            return "synced", True
        behind, ahead = StackStatus._counts(
            repo_path, f"refs/remotes/origin/{branch}", branch)
        if behind and ahead:
            return f"diverged +{ahead}/-{behind}", False
        if behind:
            return f"behind {behind}", False
        return f"ahead {ahead}", True

    def report(self, fetch_remote=False):
        """Print status and return whether the recorded stack is consistent."""
        resolver = IntegrationTargetResolver(self.manifest)
        if fetch_remote:
            for repo in self.repositories.values():
                git.fetch("origin", execution_path=repo.path,
                          raiseOnCommError=True)
        current = git.currentBranch(execution_path=self.workspace_dir)
        valid = True
        logging.info(
            f"Stack {self.manifest.name}, destination {self.manifest.destination}")
        for position, level in enumerate(self.manifest.levels, start=1):
            marker = " (*)" if level.branch == current else ""
            logging.info(
                f"  {position}. {level.branch}{marker} -> "
                f"{resolver.target(level.id)}")
            for key in sorted(level.repositories):
                state = level.repositories[key]
                repo = self.repositories.get(key)
                if not repo:
                    logging.info(f"     {key}: inactive")
                    continue
                try:
                    local_tip = git.SHA(state.branch, execution_path=repo.path)
                    target = resolver.target(level.id, key)
                    git.SHA(target, execution_path=repo.path)
                except grape_errors.GrapeGitError:
                    logging.info(f"     {key}: missing branch or target")
                    valid = False
                    continue
                behind, ahead = self._counts(repo.path, target, state.branch)
                local = "clean" if not behind and not ahead else f"ahead {ahead}"
                if behind:
                    local = f"diverged +{ahead}/-{behind}"
                    valid = False
                details = []
                if local_tip != state.tip:
                    details.append("recorded tip stale")
                    valid = False
                if (state.branch == git.currentBranch(execution_path=repo.path) and
                        git.status(
                            "--porcelain --untracked-files=no",
                            execution_path=repo.path).strip()):
                    details.append("dirty")
                    valid = False
                remote, remote_valid = self._remote_state(
                    repo.path, state.branch, state.remote_tip)
                valid = valid and remote_valid
                suffix = f"; {', '.join(details)}" if details else ""
                logging.info(
                    f"     {key}: {local}; remote {remote}{suffix}")
        return valid
