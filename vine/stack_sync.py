"""Resumable bottom-to-top synchronization for branch stacks."""

from datetime import datetime, timezone
import json
import logging
import os

from vine import grape_errors
from vine import grapeGit as git
from vine.stack import IntegrationTargetResolver, StackError, StackStore


class StackSynchronizer:
    """Plan and apply parent changes to each descendant stack branch."""

    def __init__(self, workspace_dir, manifest, repositories):
        self.workspace_dir = workspace_dir
        self.manifest = manifest
        self.repositories = {repo.key: repo for repo in repositories}
        self.store = StackStore(workspace_dir)
        self.progress_path = os.path.join(
            git.gitDir(execution_path=workspace_dir), "grape", "stack-sync.json")

    def _save_progress(self, progress):
        contents = json.dumps(progress, indent=2, sort_keys=True) + "\n"
        self.store._atomic_write(self.progress_path, contents)

    def _load_progress(self):
        try:
            with open(self.progress_path, encoding="utf-8") as stream:
                progress = json.load(stream)
        except (FileNotFoundError, ValueError) as exc:
            raise StackError("No resumable stack synchronization was found.") from exc
        if progress.get("stack_id") != self.manifest.id:
            raise StackError("The saved synchronization belongs to another stack.")
        return progress

    def _remove_progress(self):
        try:
            os.remove(self.progress_path)
        except FileNotFoundError:
            pass

    @staticmethod
    def _operation_in_progress(repo_path):
        git_dir = git.gitDir(execution_path=repo_path)
        markers = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "rebase-apply", "rebase-merge")
        return any(os.path.exists(os.path.join(git_dir, marker)) for marker in markers)

    def _validate_remote_tips(self, no_fetch):
        for level in self.manifest.levels:
            for key, state in level.repositories.items():
                repo = self.repositories.get(key)
                if not repo or state.remote_tip is None:
                    continue
                if not no_fetch:
                    git.fetch("origin", execution_path=repo.path,
                              raiseOnCommError=True)
                try:
                    observed = git.SHA(
                        f"refs/remotes/origin/{state.branch}",
                        execution_path=repo.path)
                except grape_errors.GrapeGitError as exc:
                    raise StackError(
                        f"Remote branch {state.branch!r} disappeared from {key}.") from exc
                if observed != state.remote_tip:
                    raise StackError(
                        f"Remote branch {state.branch!r} moved in {key}: expected "
                        f"{state.remote_tip}, found {observed}.")

    def _tasks(self, start_index):
        tasks = []
        for level_index in range(start_index + 1, len(self.manifest.levels)):
            child = self.manifest.levels[level_index]
            resolver = IntegrationTargetResolver(self.manifest)
            for key in child.repositories:
                repo = self.repositories.get(key)
                if not repo:
                    raise StackError(
                        f"Repository {key} participates in {child.name!r} but is inactive.")
                parent_branch = resolver.target(child.id, key)
                parent_level = None
                for candidate in reversed(self.manifest.levels[:level_index]):
                    if key in candidate.repositories:
                        parent_level = candidate
                        break
                if parent_level is None:
                    continue
                tasks.append({
                    "level_index": level_index,
                    "level_id": child.id,
                    "level_name": child.name,
                    "repository": key,
                    "branch": child.repositories[key].branch,
                    "parent_branch": parent_branch,
                    "old_parent_tip": parent_level.repositories[key].tip,
                })
        return tasks

    @staticmethod
    def _backup_ref(manifest, task, repo_path):
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        reference = (
            f"refs/grape/backups/{manifest.id}/{timestamp}/{task['level_id']}")
        tip = git.SHA(task["branch"], execution_path=repo_path)
        git.gitcmd(
            f"update-ref {reference} {tip}", "Could not create stack backup ref",
            execution_path=repo_path)
        return reference

    @staticmethod
    def _contains(repo_path, branch, ancestor):
        return git.branchUpToDateWith(branch, ancestor, execution_path=repo_path)

    def plan(self, start_index, strategy):
        """Log and return the ordered synchronization tasks."""
        tasks = self._tasks(start_index)
        logging.info(
            f"Stack {self.manifest.name}: synchronize descendants using {strategy}")
        if not tasks:
            logging.info("  No descendant branches require synchronization.")
        for task in tasks:
            repo = self.repositories[task["repository"]]
            parent_tip = git.SHA(task["parent_branch"], execution_path=repo.path)
            action = "already contains parent"
            if not self._contains(repo.path, task["branch"], parent_tip):
                action = f"{strategy} onto {task['parent_branch']}"
            logging.info(
                f"  {task['repository']}: {task['branch']} - {action}")
        return tasks

    def run(self, start_index=0, strategy="rebase", no_fetch=False,
            push=False, dry_run=False, continue_operation=False):
        """Synchronize all descendants and persist their verified tips."""
        if strategy not in ("rebase", "merge"):
            raise StackError(f"Unsupported synchronization strategy {strategy!r}.")

        if continue_operation:
            progress = self._load_progress()
            tasks = progress["tasks"]
            task_index = progress["task_index"]
            strategy = progress["strategy"]
            push = progress["push"]
            if task_index >= len(tasks):
                raise StackError("Saved synchronization has no pending task.")
            task = tasks[task_index]
            repo = self.repositories[task["repository"]]
            try:
                if strategy == "rebase":
                    git.rebase("--continue", execution_path=repo.path)
                else:
                    git.commit("--no-edit", execution_path=repo.path)
            except grape_errors.GrapeGitError:
                logging.error(
                    "Synchronization still has conflicts; resolve them and rerun "
                    "'grape stack sync --continue'.")
                return False
            progress["task_index"] += 1
            self._save_progress(progress)
        else:
            for repo in self.repositories.values():
                if self._operation_in_progress(repo.path):
                    raise StackError(
                        f"Repository {repo.key} already has an active Git operation.")
            self._validate_remote_tips(no_fetch)
            tasks = self.plan(start_index, strategy)
            if dry_run:
                return True
            progress = {
                "stack_id": self.manifest.id,
                "start_index": start_index,
                "strategy": strategy,
                "push": push,
                "task_index": 0,
                "tasks": tasks,
            }
            self._save_progress(progress)

        while progress["task_index"] < len(tasks):
            task = tasks[progress["task_index"]]
            repo = self.repositories[task["repository"]]
            parent_tip = git.SHA(task["parent_branch"], execution_path=repo.path)
            if self._contains(repo.path, task["branch"], parent_tip):
                progress["task_index"] += 1
                self._save_progress(progress)
                continue
            if not self._contains(
                    repo.path, task["branch"], task["old_parent_tip"]):
                raise StackError(
                    f"{task['branch']!r} in {repo.key} contains neither its old "
                    f"parent {task['old_parent_tip']} nor current parent {parent_tip}.")

            backup = self._backup_ref(self.manifest, task, repo.path)
            logging.info(
                f"Synchronizing {task['branch']} in {repo.key}; backup {backup}")
            git.checkout(task["branch"], execution_path=repo.path)
            try:
                if strategy == "rebase":
                    git.rebase(
                        f"--onto {task['parent_branch']} "
                        f"{task['old_parent_tip']} {task['branch']}",
                        execution_path=repo.path)
                else:
                    git.merge(f"--no-edit {task['parent_branch']}", execution_path=repo.path)
            except grape_errors.GrapeGitError:
                logging.error(
                    f"Synchronization stopped at {task['branch']} in {repo.key}. "
                    "Resolve conflicts, then run 'grape stack sync --continue'.")
                return False
            progress["task_index"] += 1
            self._save_progress(progress)

        top = self.manifest.levels[-1]
        for key, repo in self.repositories.items():
            top_state = top.repositories.get(key)
            if top_state:
                git.checkout(top_state.branch, execution_path=repo.path)

        for level in self.manifest.levels:
            for key, state in level.repositories.items():
                repo = self.repositories.get(key)
                if repo:
                    state.tip = git.SHA(state.branch, execution_path=repo.path)

        if push:
            self._push_levels(start_index, strategy)
        with self.store.locked():
            self.store.save(self.manifest)
        self._remove_progress()
        logging.info(f"Stack {self.manifest.name!r} is synchronized.")
        return True

    def _push_levels(self, start_index, strategy):
        """Push changed levels in dependency order with explicit leases."""
        for level in self.manifest.levels[start_index:]:
            for key, state in level.repositories.items():
                repo = self.repositories.get(key)
                if not repo:
                    continue
                current_tip = git.SHA(state.branch, execution_path=repo.path)
                if state.remote_tip is None:
                    git.push(f"-u origin {state.branch}", throwOnFail=True,
                             execution_path=repo.path)
                elif current_tip != state.remote_tip:
                    force = ""
                    if strategy == "rebase" or not self._contains(
                            repo.path, state.branch,
                            f"refs/remotes/origin/{state.branch}"):
                        force = (
                            f"--force-with-lease=refs/heads/{state.branch}:"
                            f"{state.remote_tip} ")
                    git.push(f"{force}origin {state.branch}", throwOnFail=True,
                             execution_path=repo.path)
                state.remote_tip = current_tip
