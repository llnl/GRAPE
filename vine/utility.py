"""GRAPE's git utility logic across multiple repositories."""
import logging
import os
import sys
from docopt.docopt import docopt
from vine import CodeReviewsFactory
from vine import grape_errors
from vine import grapeGit as git
from vine import config_parser_base
from vine import config_parser_global
from vine.option import Option
if sys.platform == 'linux2':
    import readline


# This is not configurable
GRAPE_CONFIG = '.grapeconfig'
IS_NON_INTERACTIVE = False


def ensure_dir(f):
    d = os.path.dirname(f)
    if not os.path.exists(d):
        os.makedirs(d)


def grapeDir():
    return os.path.dirname(os.path.join(os.path.realpath(os.path.dirname(__file__))))


def getDefaultName():
    if os.name == "nt":
        return os.getenv("USERNAME")
    else:
        return os.getenv("USER")


def _serviceFromCodeReviewsURL(url):
    if not url:
        return None
    url = url.lower()
    if "gitlab" in url:
        return "GitLab"
    if "bitbucket" in url or "stash" in url:
        return "Bitbucket"
    return None


def getUserName(cliArgs=None, defaultName=None, service=None):
    """
    Resolve the username for a given service.

    Precedence:
      1) CLI argument: cliArgs['--user'] (if provided and non-empty)
      2) Home grape config: $HOME/.grapeconfig [services] <service.lower()>;
         service is inferred from cliArgs['--codeReviewsURL'] when possible
      3) Interactive prompt (or default in non-interactive mode)

    If the user opts in, persist the username to:
      $HOME/.grapeconfig under [services] <service.lower()>.

    Args:
        cliArgs: Parsed CLI args dict (e.g., from docopt) that may include '--user'.
        defaultName: Default username to present in prompt; if None, uses getDefaultName().
        service: Service identifier (e.g., "GitLab"). If omitted, infer from
                 cliArgs['--codeReviewsURL'] when possible, otherwise use "LC".

    Returns:
        The resolved username (str).
    """
    # Older callers pass a username string positionally. Treat that as the
    # prompt default instead of assuming a parsed CLI args mapping.
    if isinstance(cliArgs, str):
        if defaultName is None:
            defaultName = cliArgs
        cliArgs = None

    # Use the CLI argument if provided
    if cliArgs and cliArgs.get('--user'):
        return cliArgs['--user']

    if service is None:
        service = _serviceFromCodeReviewsURL(cliArgs.get('--codeReviewsURL') if cliArgs else None) or "LC"

    # Check for a saved entry in the home grape config (not workspace/user config)
    home_dir = config_parser_global.get_env_config_path()
    home_config = config_parser_base.GrapeConfigParserBase(workspaceDir=home_dir)
    try:
        if home_config.has_section(Option.SECTION_SERVICES) and home_config.has_option(
            Option.SECTION_SERVICES, service.lower()
        ):
            service_user_name = home_config.get(Option.SECTION_SERVICES, service.lower())
            logging.info(f'Loaded user name "{service_user_name}" for service "{service}" from $HOME/.grapeconfig.')
            return service_user_name
    except Exception:
        pass

    # Ask for the username
    if defaultName is None:
        defaultName = getDefaultName()

    username = userInput(f"Enter {service} User Name:", defaultName)

    # Ask if the user wants to remember this username
    remember = userInput(f"Remember this {service} username in $HOME/.grapeconfig? (y/n)", "n")

    if remember:
        # Save the username to $HOME/.grapeconfig
        try:
            # Ensure the services section exists
            if not home_config.has_section(Option.SECTION_SERVICES):
                home_config.add_section(Option.SECTION_SERVICES)

            # Set the username for this service
            home_config.set(Option.SECTION_SERVICES, service.lower(), username)

            # Persist only the home config (avoid writing merged workspace config)
            config_path = os.path.join(home_dir, GRAPE_CONFIG)
            config_parser_global.writeConfig(home_config, config_path)

            # Update the in-memory singleton for this process, if it exists
            global_config = config_parser_global.grapeConfig()
            if not global_config.has_section(Option.SECTION_SERVICES):
                global_config.add_section(Option.SECTION_SERVICES)
            global_config.set(Option.SECTION_SERVICES, service.lower(), username)

            logging.info(f"Username for {service} saved to {config_path}")
        except Exception as e:
            logging.error(f"Failed to save username to $HOME/.grapeconfig: {e}")

    return username


def parseArgs(docstr, arguments, config):
    args = docopt(docstr, argv=arguments)
    for key in args:
        # Use config file to substitute for grape config default strings
        # Look for strings that match ".grapeconfig.<section>.<keyword>"
        if isinstance(args[key], str) and args[key].startswith(GRAPE_CONFIG) and config is not None:
            tokens = args[key].rstrip().split('.')
            if len(tokens) == 4 and tokens[0] == "":
               section = tokens[2]
               keyword = tokens[3]
               # make sure there are no spaces in the tokens
               if section.find(' ') == -1 and keyword.find(' ') == -1:
                  args[key] = config.get(section, keyword)
    return args


# ask the user for something and return what they put in
# NOTE THE SPECIAL TREATMENT for y/n/Y/N defaults:
# if default is 'y', 'n', 'Y', or 'N', this will evaluate
# to True if the user inputs 'y' or 'yes' (case-insensitive)
# and will evaluate to False if the user inputs 'n' or 'no'
# (case insensitive). Only these inputs, along with any
# inputs specified in additional_inputs are allowed.
# additional_inputs has no effect except with y/n/Y/N defaults.
def userInput(message, default=None, additional_inputs=[]):
    print(f"\n{message}")
    if IS_NON_INTERACTIVE:
        if not default:
            return ""
        elif default.lower() == "y":
            logging.info(default)
            return True
        elif default.lower() == "n":
            logging.info(default)
            return False
        else:
            logging.info(default)
            return default

    if default == "" or default is None:
        return input('==> ').strip()
    value = input(f"(def: {default}) ==> ").strip()
    if value == "":
        value = default
    if default.lower() == "y" or default.lower() == "n":
        while True:
            if value.lower() == "y":
                return True
            if value.lower() == "yes":
                return True
            if value.lower() == "n":
                return False
            if value.lower() == "no":
                return False
            if value in additional_inputs:
                return value
            print(f"Please enter {'/'.join(['y','yes','n','no'] + additional_inputs)}...")
            value = input(f"(def: {default}) ==> ").strip()
    return value


def isWorkspaceClean(printOutput=False, *, workspace_dir):
    # Imported here to avoid circular dependencies
    from vine import config_parser_user
    isClean = git.isWorkingDirectoryClean(printOutput=printOutput,
                                          execution_path=workspace_dir)
    activeNestedSubprojects = config_parser_user.getAllActiveNestedSubprojectPrefixes(workspaceDir=workspace_dir)
    for sub in activeNestedSubprojects:
        if not isClean:
            return False
        isClean = isClean and git.isWorkingDirectoryClean(
            printOutput=printOutput, execution_path=os.path.join(workspace_dir, sub))
    return isClean


def getModifiedInactiveSubmodules(branch1, branch2, includeAdded=False, *,
                                  workspace_dir):
    modifiedSubs = git.getModifiedSubmodules(workspace_dir, branch1=branch1,
                                             branch2=branch2,
                                             includeAdded=includeAdded)
    activeSubs = git.getActiveSubmodules(execution_path=workspace_dir)
    missing = []
    for sub in modifiedSubs:
        if sub not in activeSubs:
            missing.append(sub)
    return missing


# returns the absolute path to the grape executable this file is bundled with
def getGrapeExec():
    par_dir_name = os.path.dirname(os.path.dirname(__file__))
    grape_path = os.path.join(par_dir_name, "grape_main.py")
    if os.name != "nt":
        return grape_path

    grape_path = win_path_to_linux_path(grape_path)
    python_path = win_path_to_linux_path(sys.executable)
    return f"{python_path} {grape_path}"


def win_path_to_linux_path(path):
    """Convert absolute Windows path to linux path for hooks in Git bash."""
    if os.path.altsep:
       path = path.replace('C:', f'{os.path.altsep}c')
       path = path.replace(os.path.sep, os.path.altsep)
    path = path.replace(' ', f'{os.path.sep} ')
    path = path.replace('(x86)', f'{os.path.sep}(x86{os.path.sep})')
    return path


def authenticateToGitHost(user_name, workspace_dir, args):
    """
    Authenticate to the git hosting service and create a client instance.

    This method builds the connection parameters from the provided
    command line arguments, logs the target URL, and delegates client
    creation to `CodeReviewsFactory.makeCodeReviews`.

    Parameters
    ----------
    user_name : str
        The user name to authenticate as.
    workspace_dir : str
        The workspace directory.
    args : dict
        Dictionary of command line arguments, expected to contain:

        - `"--codeReviewsURL"` : str
        Base URL of the code review or Git host.
        - `"--verifySSL"` : str
        String flag indicating whether SSL certificates should be
        verified, for example `"true"` or `"false"`.
        - `"--ssh_pat_port"` : str or int
        Port number used for SSH or PAT based communication.
        - `"--ssh_pat_url"` : str
        SSH or PAT endpoint or URL segment used for authentication.

    Returns
    -------
    CodeReviews
        An instance returned by `CodeReviewsFactory.makeCodeReviews`
        configured for the given user, workspace directory, and git hosting service.

    Side Effects
    ------------
    Logs an informational message indicating the URL that is being used
    to authenticate.

    Notes
    -----
    The `"--verifySSL"` argument is treated as case insensitive; only
    the string `"true"` (ignoring case) results in certificate
    verification being enabled.
    """
    url = args['--codeReviewsURL']
    verify = True if args['--verifySSL'].lower() == 'true' else False
    logging.info(f'Logging onto {url}...')

    return CodeReviewsFactory.makeCodeReviews(
        user_name,
        url=url,
        verify=verify,
        port=int(args['--ssh_pat_port']),
        ssh_path=args['--ssh_pat_url'],
        workspace_dir=workspace_dir
    )


def is_same_path_or_child(candidate_path, parent_path):
    """Check whether one normalized path is equal to or contained by another.

    Args:
        candidate_path (str): Path being checked.
        parent_path (str): Expected ancestor path.

    Returns:
        bool: True when `candidate_path` is equal to or under `parent_path`.
    """
    try:
        return os.path.commonpath([candidate_path, parent_path]) == parent_path
    except ValueError:
        return False


def select_repo_pathspecs(requested_paths, repo_path, repo_paths):
    """Translate workspace paths into pathspecs for one repository.

    Args:
        requested_paths (list[str]): Absolute paths requested after the `--` separator.
        repo_path (str): Absolute path to the repository being diffed.
        repo_paths (list[str]): Absolute paths to all repositories participating in the diff.

    Returns:
        list[str]: Git pathspecs relative to `repo_path`.
    """
    if not requested_paths:
        return []

    child_repo_paths = [
        candidate for candidate in repo_paths
        if candidate != repo_path and is_same_path_or_child(candidate, repo_path)
    ]
    pathspecs = []
    seen = set()
    for requested_path in requested_paths:
        if is_same_path_or_child(requested_path, repo_path):
            relative_path = os.path.relpath(requested_path, repo_path)
            pathspec = "." if relative_path == "." else relative_path.replace(os.sep, "/")
        elif is_same_path_or_child(repo_path, requested_path):
            pathspec = "."
        else:
            continue
        if any(
            requested_path != child_repo_path and is_same_path_or_child(requested_path, child_repo_path)
            for child_repo_path in child_repo_paths
        ):
            continue

        if pathspec not in seen:
            pathspecs.append(pathspec)
            seen.add(pathspec)
    return pathspecs


def resolve_workspace_paths(raw_paths, *, workspace_dir, current_dir):
    """Resolve CLI path arguments into normalized workspace-local absolute paths.

    Args:
        raw_paths (list[str]): Raw path arguments provided by the user.
        workspace_dir (str): Absolute path to the workspace root.
        current_dir (str): Absolute path to the caller's current working directory.

    Returns:
        list[str]: Absolute normalized paths that fall within the workspace.
    """
    requested_paths = []
    workspace_root = os.path.realpath(workspace_dir)
    current_root = os.path.realpath(current_dir)

    for raw_path in raw_paths:
        candidate_path = raw_path if os.path.isabs(raw_path) else os.path.join(current_root, raw_path)
        absolute_path = os.path.realpath(candidate_path)
        if not is_same_path_or_child(absolute_path, workspace_root):
            logging.warning("Ignoring path outside workspace: `%s`", raw_path)
            continue
        requested_paths.append(absolute_path)
    return requested_paths


def map_ref_for_repo(ref, repo_type):
    """Translate a workspace ref for repository-specific branch naming.

    Args:
        ref (str | None): Ref named in workspace terms.
        repo_type (str): Repository classification such as `outer` or `submodule`.

    Returns:
        str: The translated ref for the target repository.
    """
    if ref is None or repo_type != "submodule":
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


def resolve_repo_ref(ref, repo_type, no_fetch, repo):
    """Resolve a workspace ref into a repository-local ref.

    Args:
        ref (str | None): Ref named at the workspace level.
        repo_type (str): Repository classification such as `outer` or `submodule`.
        no_fetch (bool): Whether to avoid fetching missing origin refs.
        repo (str): Absolute path to the repository being diffed.

    Returns:
        str: The repository-local ref to pass to `git diff`.
    """
    if ref is None:
        return None

    mapped_ref = map_ref_for_repo(ref, repo_type)
    if mapped_ref.startswith("--"):
        return mapped_ref

    resolved_ref = mapped_ref
    try:
        git.shortSHA(resolved_ref, execution_path=repo)
    except grape_errors.GrapeGitError:
        if not resolved_ref.startswith("origin/"):
            resolved_ref = git.join_list_as_git_path(["origin", resolved_ref])
        try:
            git.shortSHA(resolved_ref, execution_path=repo)
        except grape_errors.GrapeGitError:
            if not no_fetch and resolved_ref.startswith("origin/"):
                try:
                    git.fetch("origin", resolved_ref.partition("/")[2], execution_path=repo)
                except grape_errors.GrapeGitError:
                    # Let the later diff attempt surface a concise warning if the ref still cannot be used.
                    pass

    return resolved_ref
