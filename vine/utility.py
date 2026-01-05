"""GRAPE's git utility logic across multiple repositories."""
import logging
import os
import sys
from docopt.docopt import docopt
from vine import CodeReviewsFactory
from vine import grapeGit as git
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


def getUserName(cliArgs=None, defaultName=None, service="LC"):
    """
    Resolve the username for a given service.

    Precedence:
      1) CLI argument: cliArgs['--user'] (if provided and non-empty)
      2) Global grape config: [services] <service.lower()>
      3) Interactive prompt (or default in non-interactive mode)

    If the user opts in, persist the username to:
      <workspace>/.git/.grapeuserconfig under [services] <service.lower()>.

    Args:
        cliArgs: Parsed CLI args dict (e.g., from docopt) that may include '--user'.
        defaultName: Default username to present in prompt; if None, uses getDefaultName().
        service: Service identifier (e.g., "LC"); stored/looked up as lowercase.

    Returns:
        The resolved username (str).
    """
    # Use the CLI argument if provided
    if cliArgs and cliArgs.get('--user'):
        return cliArgs['--user']

    # Check for a saved entry in the grape user config
    config = config_parser_global.grapeConfig()

    try:
        if config.has_section(Option.SECTION_SERVICES) and config.has_option(Option.SECTION_SERVICES, service.lower()):
            return config.get(Option.SECTION_SERVICES, service.lower())
    except:
        pass

    # Ask for the username
    if defaultName is None:
        defaultName = getDefaultName()

    username = userInput(f"Enter {service} User Name:", defaultName)

    # Ask if the user wants to remember this username
    remember = userInput(f"Remember this {service} username in .grapeuserconfig? (y/n)", "n")

    if remember:
        # Save the username to .grapeuserconfig
        try:
            from vine import config_parser_user
            import os

            # Get the workspace directory
            workspace_dir = os.getcwd()

            # Create a user config parser
            user_config = config_parser_user.GrapeConfigParserUser(workspace_dir=workspace_dir)

            # Ensure the services section exists
            if not user_config.has_section(Option.SECTION_SERVICES):
                user_config.add_section(Option.SECTION_SERVICES)

            # Set the username for this service
            user_config.set(Option.SECTION_SERVICES, service.lower(), username)

            # Save the config to .grapeuserconfig
            git_dir = os.path.join(workspace_dir, '.git')
            config_path = os.path.join(git_dir, '.grapeuserconfig')

            # Ensure the directory exists
            if not os.path.exists(git_dir):
                os.makedirs(git_dir)

            with open(config_path, 'w') as f:
                user_config.write(f)

            print(f"Username for {service} saved to {config_path}")
        except Exception as e:
            print(f"Failed to save username to .grapeuserconfig: {e}")

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
# to True if the user inputs anything that starts with a 'y' or 'Y',
# and will evaluate to False if the user inputs anything that starts
# with a 'N' or 'n'.
def userInput(message, default=None):
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
        if value.lower()[0] == "y":
            return True
        if value.lower()[0] == "n":
            return False
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
        logging.info(f'Logging onto {url}')

        return CodeReviewsFactory.makeCodeReviews(
            user_name,
            url=url,
            verify=verify,
            port=int(args['--ssh_pat_port']),
            ssh_path=args['--ssh_pat_url'],
            workspace_dir=workspace_dir
        )