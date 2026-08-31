"""Validation and conservative recovery for local branch stacks."""

import logging

from vine import grape_errors
from vine import grapeGit as git
from vine.stack import IntegrationTargetResolver, StackStore


class StackValidator:
    """Validate recorded stack structure against local and remote Git facts."""

    def __init__(self, workspace_dir, manifest, repositories):
        self.workspace_dir = workspace_dir
        self.manifest = manifest
        self.repositories = {repo.key: repo for repo in repositories}
        self.errors = []
        self.repairs = []

    def _error(self, message):
        """Record and display one validation failure."""
        self.errors.append(message)
        logging.info(f"  ERROR: {message}")

    def _repair(self, message):
        """Record and display one manifest repair."""
        self.repairs.append(message)
        logging.info(f"  REPAIRED: {message}")

    def _validate_identity(self):
        """Reject missing or duplicate stable IDs and level identities."""
        if not self.manifest.id:
            self._error("stack stable ID is missing")
        if not self.manifest.levels:
            self._error("stack has no levels")
        seen_ids = set()
        seen_names = set()
        seen_branches = set()
        for position, level in enumerate(self.manifest.levels, start=1):
            label = f"level {position}"
            if not level.id:
                self._error(f"{label} stable ID is missing")
            elif level.id in seen_ids:
                self._error(f"{label} repeats stable ID {level.id!r}")
            seen_ids.add(level.id)
            if not level.name:
                self._error(f"{label} name is missing")
            elif level.name in seen_names:
                self._error(f"{label} repeats name {level.name!r}")
            seen_names.add(level.name)
            if not level.branch:
                self._error(f"{label} branch is missing")
            elif level.branch in seen_branches:
                self._error(f"{label} repeats branch {level.branch!r}")
            seen_branches.add(level.branch)
            if "." not in level.repositories:
                self._error(f"{label} does not record the outer repository")
            elif level.repositories["."].branch != level.branch:
                self._error(
                    f"{label} outer branch does not match {level.branch!r}")

    @staticmethod
    def _local_tip(repo_path, branch):
        """Return a local branch tip, or ``None`` when the branch is absent."""
        try:
            return git.SHA(f"refs/heads/{branch}", execution_path=repo_path)
        except grape_errors.GrapeGitError:
            return None

    @staticmethod
    def _remote_tip(repo_path, branch):
        """Return an origin tracking tip, or ``None`` when it is absent."""
        try:
            return git.SHA(
                f"refs/remotes/origin/{branch}", execution_path=repo_path)
        except grape_errors.GrapeGitError:
            return None

    @staticmethod
    def _is_ancestor(repo_path, ancestor, branch):
        """Return whether ``ancestor`` is contained by ``branch``."""
        try:
            git.SHA(ancestor, execution_path=repo_path)
            return git.branchUpToDateWith(
                branch, ancestor, execution_path=repo_path)
        except grape_errors.GrapeGitError:
            return False

    def _validate_repository_state(self, resolver, level, key, state,
                                   check_remote, repair):
        """Validate one physical repository record."""
        repo = self.repositories.get(key)
        if not repo:
            logging.info(
                f"  SKIPPED: {level.name} in {key} is not active in this view")
            return

        local_tip = self._local_tip(repo.path, state.branch)
        if local_tip is None:
            self._error(
                f"{level.name} in {key} is missing local branch {state.branch!r}")
            return

        target = resolver.target(level.id, key)
        try:
            git.SHA(target, execution_path=repo.path)
        except grape_errors.GrapeGitError:
            self._error(
                f"{level.name} in {key} is missing target {target!r}")
            return
        contains_target = self._is_ancestor(repo.path, target, state.branch)
        if not contains_target:
            self._error(
                f"{level.name} in {key} does not contain target {target!r}")

        remote_valid = True
        if check_remote:
            observed = self._remote_tip(repo.path, state.branch)
            if state.remote_tip is None and observed is not None:
                self._error(
                    f"{level.name} in {key} has an unrecorded remote branch at "
                    f"{observed}")
                remote_valid = False
            elif state.remote_tip is not None and observed is None:
                self._error(
                    f"{level.name} in {key} is missing its recorded remote branch")
                remote_valid = False
            elif (state.remote_tip is not None and
                  observed != state.remote_tip):
                self._error(
                    f"{level.name} in {key} remote moved from "
                    f"{state.remote_tip} to {observed}")
                remote_valid = False

        if local_tip != state.tip:
            safely_advanced = (
                contains_target and remote_valid and
                self._is_ancestor(repo.path, state.tip, state.branch))
            if repair and safely_advanced:
                old_tip = state.tip
                state.tip = local_tip
                self._repair(
                    f"{level.name} in {key} tip {old_tip} -> {local_tip}")
            elif repair:
                self._error(
                    f"{level.name} in {key} recorded tip diverged; refusing repair")
            else:
                self._error(
                    f"{level.name} in {key} recorded tip is stale")

    def run(self, fetch_remote=False, repair=False):
        """Validate the manifest and optionally repair safe tip advances.

        Args:
            fetch_remote: Fetch active repositories before remote-tip checks.
            repair: Persist local tip advances that retain the recorded tip.

        Returns:
            bool: True when the stack is valid after any requested repairs.
        """
        logging.info(f"Stack {self.manifest.name}: validate")
        self._validate_identity()
        if fetch_remote:
            for repo in self.repositories.values():
                try:
                    git.fetch(
                        "origin", execution_path=repo.path,
                        raiseOnCommError=True)
                except grape_errors.GrapeGitError as exc:
                    self._error(f"could not fetch {repo.key}: {exc}")

        resolver = IntegrationTargetResolver(self.manifest)
        for level in self.manifest.levels:
            for key, state in sorted(level.repositories.items()):
                self._validate_repository_state(
                    resolver, level, key, state, fetch_remote, repair)

        if repair and self.repairs:
            store = StackStore(self.workspace_dir)
            with store.locked():
                store.save(self.manifest)

        if self.errors:
            logging.info(
                f"Stack {self.manifest.name!r} is invalid "
                f"({len(self.errors)} error(s)).")
            return False
        logging.info(f"Stack {self.manifest.name!r} is valid.")
        return True
