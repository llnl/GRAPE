"""Local stacked-branch model and command implementation.

A stack manifest is workspace-local state stored below ``.git/grape/stacks``.
It deliberately does not change the meaning of configured public branches.
Commands that need the immediate parent use :class:`IntegrationTargetResolver`.
"""

from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import logging
import os
import re
import tempfile
import uuid

from vine import config_parser_global
from vine import config_parser_user
from vine import grape_errors
from vine import grapeGit as git
from vine import utility
from vine.option import Option
from vine.workspace_dir_handler import WorkspaceDirHandler


MANIFEST_VERSION = 1
_SLUG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class StackError(Exception):
    """Raised when stack state or an operation is invalid."""


def _now():
    """Return a stable UTC timestamp for persisted state."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _new_id():
    """Return a stable opaque identifier suitable for a stack object."""
    return str(uuid.uuid4())


def _require_slug(value, label):
    """Validate a user-facing name used in a branch path.

    Args:
        value: Candidate stack, level, type, or user name.
        label: Name used in an error message.

    Returns:
        The original value.

    Raises:
        StackError: If the candidate is empty or unsafe in a branch path.
    """
    if not value or not _SLUG_PATTERN.fullmatch(value):
        raise StackError(
            f"Invalid {label} {value!r}; use letters, digits, '.', '-', or '_'.")
    return value


@dataclass
class StackRepository:
    """The physical branch realizing one logical level in a repository."""

    branch: str
    target: str
    tip: str
    remote_tip: str = None

    @classmethod
    def from_dict(cls, data):
        """Build a repository record from manifest JSON data."""
        return cls(
            branch=data["branch"],
            target=data["target"],
            tip=data["tip"],
            remote_tip=data.get("remote_tip"),
        )


@dataclass
class StackLevel:
    """One ordered logical change in a stack."""

    id: str
    name: str
    branch: str
    repositories: dict = field(default_factory=dict)
    created_at: str = field(default_factory=_now)

    @classmethod
    def from_dict(cls, data):
        """Build a level from manifest JSON data."""
        repositories = {
            key: StackRepository.from_dict(value)
            for key, value in data.get("repositories", {}).items()
        }
        return cls(
            id=data["id"],
            name=data["name"],
            branch=data["branch"],
            repositories=repositories,
            created_at=data.get("created_at", _now()),
        )


@dataclass
class StackManifest:
    """Versioned local source of truth for a personal linear stack."""

    id: str
    name: str
    owner: str
    branch_type: str
    start: str
    destination: str
    levels: list = field(default_factory=list)
    version: int = MANIFEST_VERSION
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    @classmethod
    def create(cls, name, owner, branch_type, start, destination):
        """Create a new, empty manifest."""
        return cls(
            id=_new_id(),
            name=name,
            owner=owner,
            branch_type=branch_type,
            start=start,
            destination=destination,
        )

    @classmethod
    def from_dict(cls, data):
        """Build and validate a manifest from decoded JSON.

        Raises:
            StackError: If the manifest uses an unsupported schema.
        """
        version = data.get("version")
        if version != MANIFEST_VERSION:
            raise StackError(
                f"Unsupported stack manifest version {version!r}; "
                f"expected {MANIFEST_VERSION}.")
        return cls(
            id=data["id"],
            name=data["name"],
            owner=data["owner"],
            branch_type=data["branch_type"],
            start=data["start"],
            destination=data["destination"],
            levels=[StackLevel.from_dict(item) for item in data.get("levels", [])],
            version=version,
            created_at=data.get("created_at", _now()),
            updated_at=data.get("updated_at", _now()),
        )

    def to_dict(self):
        """Return this manifest as JSON-compatible data."""
        return asdict(self)

    def level(self, selector):
        """Find a level by ID, name, or branch."""
        for level in self.levels:
            if selector in (level.id, level.name, level.branch):
                return level
        return None

    def index(self, selector):
        """Return a matching level's zero-based position."""
        for index, level in enumerate(self.levels):
            if selector in (level.id, level.name, level.branch):
                return index
        raise StackError(f"No level {selector!r} exists in stack {self.name!r}.")


class StackStore:
    """Atomically persist stack manifests below the outer Git directory."""

    def __init__(self, workspace_dir):
        self.workspace_dir = os.path.realpath(workspace_dir)
        self.root = os.path.join(
            git.gitDir(execution_path=self.workspace_dir), "grape", "stacks")
        self.active_path = os.path.join(self.root, "active")
        self.lock_path = os.path.join(self.root, "lock")

    def _manifest_path(self, stack_id):
        return os.path.join(self.root, f"{stack_id}.json")

    @contextmanager
    def locked(self):
        """Hold a short-lived exclusive store lock.

        Raises:
            StackError: If another process is updating stack state.
        """
        os.makedirs(self.root, exist_ok=True)
        try:
            descriptor = os.open(
                self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise StackError(
                "Another grape stack operation is updating this workspace.") from exc
        try:
            os.write(descriptor, str(os.getpid()).encode("ascii"))
            os.close(descriptor)
            yield
        finally:
            try:
                os.close(descriptor)
            except OSError:
                pass
            try:
                os.remove(self.lock_path)
            except FileNotFoundError:
                pass

    @staticmethod
    def _atomic_write(path, contents):
        """Write text beside its destination and atomically replace it."""
        parent = os.path.dirname(path)
        os.makedirs(parent, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".tmp-", dir=parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(contents)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)

    def save(self, manifest, make_active=True):
        """Atomically save a manifest and optionally select it."""
        manifest.updated_at = _now()
        contents = json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n"
        self._atomic_write(self._manifest_path(manifest.id), contents)
        if make_active:
            self._atomic_write(self.active_path, manifest.id + "\n")

    def load_id(self, stack_id):
        """Load a manifest by its stable ID."""
        path = self._manifest_path(stack_id)
        try:
            with open(path, encoding="utf-8") as stream:
                return StackManifest.from_dict(json.load(stream))
        except FileNotFoundError as exc:
            raise StackError(f"Stack manifest {stack_id!r} does not exist.") from exc
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise StackError(f"Stack manifest {path} is invalid: {exc}") from exc

    def list(self):
        """Return all readable manifests in stable name order."""
        if not os.path.isdir(self.root):
            return []
        manifests = []
        for filename in os.listdir(self.root):
            if filename.endswith(".json"):
                manifests.append(self.load_id(filename[:-5]))
        return sorted(manifests, key=lambda stack: (stack.name, stack.created_at))

    def active(self):
        """Load the explicitly active stack, if any."""
        try:
            with open(self.active_path, encoding="utf-8") as stream:
                stack_id = stream.read().strip()
        except FileNotFoundError:
            return None
        return self.load_id(stack_id) if stack_id else None

    def find(self, selector=None, branch=None):
        """Resolve a stack by selector, current branch, or active pointer."""
        manifests = self.list()
        if selector:
            matches = [
                stack for stack in manifests
                if selector in (stack.id, stack.name)
            ]
            if not matches:
                raise StackError(f"No stack named {selector!r} exists.")
            if len(matches) > 1:
                raise StackError(f"Stack name {selector!r} is ambiguous; use its ID.")
            return matches[0]
        if branch:
            matches = [stack for stack in manifests if stack.level(branch)]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise StackError(
                    f"Branch {branch!r} belongs to multiple local stacks.")
        return self.active()


@dataclass(frozen=True)
class WorkspaceRepository:
    """An active physical repository in a GRAPE workspace."""

    key: str
    path: str
    kind: str


class WorkspaceInventory:
    """Discover and validate active repositories for a stack operation."""

    def __init__(self, workspace_dir):
        self.workspace_dir = os.path.realpath(workspace_dir)

    def repositories(self, include_submodules=True, include_nested=True):
        """Return active child repositories followed by the outer repository."""
        repositories = []
        if include_nested:
            for prefix in config_parser_user.getAllActiveNestedSubprojectPrefixes(
                    workspaceDir=self.workspace_dir):
                repositories.append(WorkspaceRepository(
                    key=git.join_list_as_git_path(["nested", prefix]),
                    path=os.path.join(self.workspace_dir, prefix),
                    kind="nested",
                ))
        if include_submodules:
            for prefix in git.getActiveSubmodules(execution_path=self.workspace_dir):
                repositories.append(WorkspaceRepository(
                    key=git.join_list_as_git_path(["submodule", prefix]),
                    path=os.path.join(self.workspace_dir, prefix),
                    kind="submodule",
                ))
        repositories.append(WorkspaceRepository(".", self.workspace_dir, "outer"))
        return repositories

    @staticmethod
    def require_clean(repositories, allow_untracked=False):
        """Reject dirty worktrees before a multi-repository mutation.

        Args:
            repositories: Physical repositories to inspect.
            allow_untracked: Ignore untracked files when the operation only
                creates and checks out a branch, which preserves those files.
        """
        status_args = "--porcelain"
        if allow_untracked:
            status_args += " --untracked-files=no"
        dirty = [repo.key for repo in repositories
                 if git.status(status_args, execution_path=repo.path).strip()]
        if dirty:
            raise StackError("Dirty repositories: " + ", ".join(dirty))

    @staticmethod
    def require_same_branch(repositories, branch):
        """Reject repositories not checked out at the logical stack level."""
        inconsistent = []
        for repo in repositories:
            current = git.currentBranch(execution_path=repo.path)
            if current != branch:
                inconsistent.append(f"{repo.key} ({current})")
        if inconsistent:
            raise StackError(
                f"Expected branch {branch!r} in every active repository; found " +
                ", ".join(inconsistent))


class IntegrationTargetResolver:
    """Resolve immediate stack parents without changing public targets."""

    def __init__(self, manifest):
        self.manifest = manifest

    def target(self, level_selector, repository_key="."):
        """Return the nearest usable lower branch or publication destination."""
        index = self.manifest.index(level_selector)
        for lower in reversed(self.manifest.levels[:index]):
            state = lower.repositories.get(repository_key)
            if state:
                return state.branch
        current = self.manifest.levels[index].repositories.get(repository_key)
        if current:
            return current.target
        return self.manifest.destination


def integration_target_for_branch(branch, workspace_dir, repository_key="."):
    """Return a recorded integration target, or ``None`` outside a stack."""
    store = StackStore(workspace_dir)
    manifest = store.find(branch=branch)
    if not manifest:
        return None
    return IntegrationTargetResolver(manifest).target(branch, repository_key)


def _submodule_public_target(config, logical_destination, branch_type):
    """Map a logical destination to the corresponding submodule branch."""
    try:
        public_mapping = config.getMapping(
            Option.SECTION_WORKSPACE, "submodulepublicmappings")
        return public_mapping[logical_destination]
    except (KeyError, ValueError):
        topic_mapping = config.getMapping(
            Option.SECTION_WORKSPACE, "submoduleTopicPrefixMappings")
        return topic_mapping[branch_type]


def _repo_start_and_destination(repo, config, start, destination, branch_type):
    """Resolve the bottom start and destination for one repository."""
    if repo.kind != "submodule":
        return start, destination
    return (
        _submodule_public_target(config, start, branch_type),
        _submodule_public_target(config, destination, branch_type),
    )


def _remote_tip(repo_path, branch):
    """Return a known origin tip without making a network request."""
    try:
        return git.SHA(f"refs/remotes/origin/{branch}", execution_path=repo_path)
    except grape_errors.GrapeGitError:
        return None


def _format_branch(config, branch_type, owner, stack_name, level_name):
    """Expand the configured position-independent branch format."""
    template = config.get(
        Option.SECTION_STACK, "branchFormat", raw=True,
        fallback="<type>/<user>/<stack>/<level>")
    values = {
        "<type>": branch_type,
        "<user>": owner,
        "<stack>": stack_name,
        "<level>": level_name,
    }
    branch = template
    for token, value in values.items():
        branch = branch.replace(token, value)
    if any(token in branch for token in values):
        raise StackError(f"Invalid stack branch format {template!r}.")
    return branch


def _branch_exists(repo_path, branch):
    try:
        git.SHA(f"refs/heads/{branch}", execution_path=repo_path)
        return True
    except grape_errors.GrapeGitError:
        return False


def _print_plan(action, stack, level, repositories, targets):
    logging.info(f"Stack {stack.name}: {action} level {level.name}")
    for repo in repositories:
        logging.info(
            f"  {repo.key}: {level.branch} from {targets[repo.key]}")


class StackOption(Option, WorkspaceDirHandler):
    """
    Create and manage a linear stack of GRAPE workspace branches.

    Usage: grape-stack start <stack> <level> [--type=<type>]
                       [--start=<branch>] [--target=<branch>] [--user=<user>]
                       [--nopush] [--dry-run] [--recurse | --noRecurse]
           grape-stack add <level> [--stack=<stack>] [--nopush] [--dry-run]
                       [--recurse | --noRecurse]

    Options:
        --type=<type>       Topic prefix for generated branches. [default: feature]
        --start=<branch>    Branch from which the bottom level starts.
        --target=<branch>   Ultimate publication destination.
        --user=<user>       Branch owner. Defaults to the configured GRAPE user.
        --stack=<stack>     Stack name or stable ID. Defaults to current/active stack.
        --nopush            Do not push newly created branches.
        --dry-run           Print the complete repository plan without changing state.
        --recurse           Include active submodules and nested subprojects.
        --noRecurse         Only operate on the outer repository.
    """

    def __init__(self):
        super(StackOption, self).__init__()
        self._key = "stack"
        self._section = "Gitflow Tasks"

    def description(self):
        return "Create and manage stacked workspace branches"

    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_STACK)
        config.set(self.SECTION_STACK, "enabled", "True")
        config.set(
            self.SECTION_STACK, "branchFormat",
            "<type>/<user>/<stack>/<level>")
        config.set(self.SECTION_STACK, "syncStrategy", "rebase")
        config.set(
            self.SECTION_STACK, "submitDescendantsForReviewAsDraft", "True")
        config.set(self.SECTION_STACK, "autoRetarget", "True")
        config.set(self.SECTION_STACK, "useProviderDependencies", "True")
        config.set(self.SECTION_STACK, "deleteLandedBranches", "False")

    def execute(self, args):
        try:
            if args["start"]:
                return self._start(args)
            if args["add"]:
                return self._add(args)
        except StackError as exc:
            logging.error(f"GRAPE: STACK ERROR: {exc}")
            return False
        return False

    def _recurse(self, args, config):
        recurse = config.getboolean(
            self.SECTION_WORKSPACE, "manageSubmodules", fallback=True)
        if args["--recurse"]:
            recurse = True
        if args["--noRecurse"]:
            recurse = False
        return recurse

    def _start(self, args):
        config = config_parser_global.grapeConfig()
        if not config.getboolean(self.SECTION_STACK, "enabled", fallback=True):
            raise StackError("Stack support is disabled by [stack].enabled.")
        name = _require_slug(args["<stack>"], "stack name")
        level_name = _require_slug(args["<level>"], "level name")
        branch_type = _require_slug(args["--type"], "branch type")
        owner = _require_slug(args["--user"] or utility.getUserName(), "user")
        start = args["--start"]
        if not start:
            start = config.getMapping(
                self.SECTION_FLOW, "topicPrefixMappings")[branch_type]
        branch = _format_branch(
            config, branch_type, owner, name, level_name)
        destination = args["--target"] or config.getPublicBranchFor(branch)
        store = StackStore(self.workspace_dir)
        if any(stack.name == name for stack in store.list()):
            raise StackError(f"Stack {name!r} already exists.")

        recurse = self._recurse(args, config)
        repositories = WorkspaceInventory(self.workspace_dir).repositories(
            include_submodules=recurse, include_nested=recurse)
        targets = {}
        destinations = {}
        for repo in repositories:
            targets[repo.key], destinations[repo.key] = (
                _repo_start_and_destination(
                    repo, config, start, destination, branch_type))
            try:
                git.SHA(targets[repo.key], execution_path=repo.path)
            except grape_errors.GrapeGitError as exc:
                raise StackError(
                    f"Start branch {targets[repo.key]!r} does not exist in "
                    f"{repo.key}.") from exc

        manifest = StackManifest.create(
            name, owner, branch_type, start, destination)
        level = StackLevel(_new_id(), level_name, branch)
        _print_plan("start", manifest, level, repositories, targets)
        if args["--dry-run"]:
            return True

        with store.locked():
            for repo in repositories:
                exists = _branch_exists(repo.path, branch)
                current = git.currentBranch(execution_path=repo.path)
                if exists and current != branch:
                    raise StackError(
                        f"Branch {branch!r} already exists in {repo.key}.")
                if not exists:
                    git.checkout(
                        f"-b {branch} {targets[repo.key]}", execution_path=repo.path)
                tip = git.SHA(branch, execution_path=repo.path)
                if not git.branchUpToDateWith(
                        branch, targets[repo.key], execution_path=repo.path):
                    raise StackError(
                        f"Branch {branch!r} does not contain its start "
                        f"{targets[repo.key]!r} in {repo.key}.")
                if not args["--nopush"]:
                    git.push(f"-u origin {branch}", execution_path=repo.path)
                level.repositories[repo.key] = StackRepository(
                    branch=branch,
                    target=destinations[repo.key],
                    tip=tip,
                    remote_tip=_remote_tip(repo.path, branch),
                )
            manifest.levels.append(level)
            store.save(manifest)
        logging.info(f"Created stack {name!r} on {branch}.")
        return True

    def _add(self, args):
        config = config_parser_global.grapeConfig()
        store = StackStore(self.workspace_dir)
        current = git.currentBranch(execution_path=self.workspace_dir)
        manifest = store.find(args["--stack"], branch=current)
        if not manifest:
            raise StackError("No active stack; run 'grape stack start' first.")
        if not manifest.levels:
            raise StackError(f"Stack {manifest.name!r} has no bottom level.")
        parent = manifest.levels[-1]
        if current != parent.branch:
            raise StackError(
                f"New levels can only be added above stack top {parent.branch!r}; "
                f"current branch is {current!r}.")
        level_name = _require_slug(args["<level>"], "level name")
        if manifest.level(level_name):
            raise StackError(f"Level {level_name!r} already exists.")
        branch = _format_branch(
            config, manifest.branch_type, manifest.owner,
            manifest.name, level_name)
        recurse = self._recurse(args, config)
        repositories = WorkspaceInventory(self.workspace_dir).repositories(
            include_submodules=recurse, include_nested=recurse)
        WorkspaceInventory.require_clean(repositories, allow_untracked=True)
        WorkspaceInventory.require_same_branch(repositories, parent.branch)
        targets = {repo.key: parent.branch for repo in repositories}
        level = StackLevel(_new_id(), level_name, branch)
        _print_plan("add", manifest, level, repositories, targets)
        if args["--dry-run"]:
            return True

        with store.locked():
            # The top level may have received commits since it was first
            # recorded. Capture its actual tip before creating the child so
            # later synchronization can replay from the correct parent.
            for repo in repositories:
                parent_state = parent.repositories.get(repo.key)
                if parent_state:
                    parent_state.tip = git.SHA(
                        parent_state.branch, execution_path=repo.path)
                    parent_state.remote_tip = _remote_tip(
                        repo.path, parent_state.branch)
            for repo in repositories:
                if _branch_exists(repo.path, branch):
                    raise StackError(
                        f"Branch {branch!r} already exists in {repo.key}.")
            for repo in repositories:
                git.checkout(f"-b {branch} {parent.branch}", execution_path=repo.path)
                if not args["--nopush"]:
                    git.push(f"-u origin {branch}", execution_path=repo.path)
                parent_state = parent.repositories.get(repo.key)
                target = parent_state.branch if parent_state else manifest.destination
                level.repositories[repo.key] = StackRepository(
                    branch=branch,
                    target=target,
                    tip=git.SHA(branch, execution_path=repo.path),
                    remote_tip=_remote_tip(repo.path, branch),
                )
            manifest.levels.append(level)
            store.save(manifest)
        logging.info(f"Added {level_name!r} to stack {manifest.name!r}.")
        return True


def main():
    """Run the stack command through GRAPE's menu."""
    from vine import grapeMenu
    grapeMenu.menu().applyMenuChoice("stack", [])


if __name__ == "__main__":
    main()
