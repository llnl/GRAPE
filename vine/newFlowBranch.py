import logging
import os
from vine import checkout
from vine import config_parser_global
from vine import grape_errors
from vine import grapeGit as git
from vine import multi_repo_cmd_launcher
from vine import updateView
from vine import utility
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.option import Option
from vine.vine_logging import log_wrapper


class NewBranchOption(Option, WorkspaceDirHandler):
    """
    grape <newtopicbranch>
    Creates a new topic branch <type>/<username>/<descr> off of a public <branch>, where <type> is read from
    one of the <type>:<branch> pairs found in .grapeconfig.flow.topicPrefixMappings.

    Usage: grape-<type> [--start=<branch>] [--user=<username>] [--noverify] [--recurse | --noRecurse] [<descr>]

    Options:
    --user=<username>       The user developing this branch. Asks by default.
    --start=<branch>        The start point for this branch. Default comes from .grapeconfig.flow.topicPrefixMappings.
    --noverify              By default, grape will ask the user to verify the name and start point of the branch.
                            This disables the verification.
    --recurse               Create the branch in submodules.
                            [default: .grapeconfig.workspace.manageSubmodules]
    --noRecurse             Don't create the branch in submodules.

    Optional Arguments:
    <descr>                  Single word description of work being done on this branch. Asks by default.


    """
    def __init__(self, topic, public):
        super(NewBranchOption, self).__init__()
        self._key = topic
        if (topic != topic.lower()):
            logging.warning(
                f"WARNING: {topic} in .grapeconfig.flow.topicPrefixMappings" +
                " should be lowercase.")
            self._key = topic.lower()
        self._section = "Gitflow Tasks"
        self._public = public

    def description(self):
        return f"Create and switch to a {self._key} branch off of {self._public}"



    @log_wrapper
    def execute(self, args):
        # Imported here to avoid circular dependencies
        from vine import grapeMenu

        start = args["--start"]
        if not start:
            start = self._public

        config = config_parser_global.grapeConfig()

        # decide whether to recurse
        recurse = config.get(self.SECTION_WORKSPACE, 'manageSubmodules')
        if args["--recurse"]:
            recurse = True
        if args["--noRecurse"]:
            recurse = False


        if not args["<descr>"]:
            args["<descr>"] =  utility.userInput("Enter one word description for branch:")

        if not args["--user"]:
            args["--user"] = utility.getUserName()

        if args["--user"] != args["--user"].lower():
            utility.userInput("Converting username to lowercase.  Press any key to continue...")
            args["--user"] = args["--user"].lower()

        branchName = git.join_list_as_git_path([self._key, args["--user"], args["<descr>"]])

        branchStatus = checkout.branchAlreadyExists(branchName,
                                                    self.workspace_dir)
        if branchStatus:
            logging.info("Not creating new branch.")
            if branchStatus == 1:
                logging.info(f"Use `grape checkout {branchName}' instead.")
            return False

        activeSubmodulesCheck = git.getActiveSubmodules(execution_path=self.workspace_dir)

        addedModules = []
        removedModules = []
        changedURLModules = []
        if recurse:
            checkout.parseGitModulesDiffOutput(
                git.currentBranch(execution_path=self.workspace_dir), start, addedModules,
                removedModules, changedURLModules,
                workspace_dir=self.workspace_dir)
            # deinit and clean out any submodules that changed urls or
            # are not present in the public branch.
            for sub in changedURLModules + removedModules:
                url_update = "has changed URL" if sub in changedURLModules else f"is not present in {start}"
                maybe_active = "active" if sub in activeSubmodulesCheck else "inactive"
                logging.info(
                    f"{sub} {url_update}, attempting to remove references " +
                    f"for {maybe_active} submodule before branch creation.")
                cleaned = checkout.cleanSubmodule(sub, args, True, activeSubmodulesCheck, workspace_dir=self.workspace_dir)
                if not cleaned:
                    logging.info(f"Failed to remove old submodule for {sub}.")
                    return False

        # Determine whether the public branch for the current branch is the
        # same as the public branch for the new branch.
        checkoutBeforeCreate = True
        try:
            currentBranch = git.currentBranch(execution_path=self.workspace_dir)
            if currentBranch in config.get(Option.SECTION_FLOW, 'publicBranches'):
               currentPublic = currentBranch
            else:
               currentPublic = config.getPublicBranchFor(currentBranch)
            if currentPublic == start:
               checkoutBeforeCreate = False
        except:
            pass


        if checkoutBeforeCreate:
            logging.info(f"Checking out public branch {start} before branch creation...")

            updateView.safeSwitchWorkspaceToBranch(branch=start, checkoutArgs="", sync=False, workspace_dir=self.workspace_dir)
            # Re-read the grape config from the new public branch
            config_parser_global.resetGrapeConfig()
            config_parser_global.read(workspace_dir=self.workspace_dir)
            config = config_parser_global.grapeConfig()


        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(createBranch,
                                                   runInSubmodules=recurse,
                                                   runInSubprojects=recurse,
                                                   runInOuter=True,
                                                   branch=start,
                                                   globalArgs=branchName,
                                                   workspace_dir=self.workspace_dir)
        launcher.initializeCommands()
        logging.info("About to create the following branches:")
        for repo, branch in zip(launcher.repos, launcher.branches):
            logging.info(f"\t{branchName} off of {branch} in {repo}")
        proceed = utility.userInput("Proceed? [y/n]", default="y")
        if proceed:
            menu = grapeMenu.menu(workspace_dir=self.workspace_dir)
            menu.applyMenuChoice('up', ['up', f'--public={start}'])
            launcher.launchFromWorkspaceDir()
        else:
            logging.info("branches not created")

        # reinit any submodules with changed URLs
        for sub in changedURLModules:
            if sub in activeSubmodulesCheck:
                git.submodule(f"update --init {sub}", execution_path=self.workspace_dir)
                # If there is already a branch by this name in the new repo,
                # this will reset the branch.
                sub_dir = os.path.join(self.workspace_dir, sub)
                git.checkout(f"-B {branchName}", execution_path=sub_dir)

        return True

    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_WORKSPACE)
        config.set(self.SECTION_WORKSPACE, 'manageSubmodules', 'True')
        config.set(self.SECTION_WORKSPACE, 'submoduleTopicPrefixMappings', '?:develop')


class NewBranchOptionFactory:

    @staticmethod
    def createNewBranchOptions(config, *, execution_path):
        topicPublicMapping = config.getMapping(Option.SECTION_FLOW, 'topicPrefixMappings')
        options = []
        for topic in topicPublicMapping.keys():
            if topic != '?':
                new_branch_option = NewBranchOption(topic,
                                                    topicPublicMapping[topic])
                new_branch_option.workspace_dir = execution_path
                options.append(new_branch_option)
        return options


def createBranch(repo="unknown", branch="master", args=[], *, workspace_dir):
    branchPoint = branch
    fullBranch = args
    logging.info(f"creating and switching to {fullBranch} in {repo}")
    try:
        git.checkout(f"-b {fullBranch} {branchPoint} ",
                     execution_path=repo)
    except grape_errors.GrapeGitError as e:
        logging.error(f"{repo}:{e.gitOutput}")
        logging.warning(f"WARNING: {fullBranch} in {repo}" +
                        " will not be pushed.")
        return
    logging.info(f"pushing {fullBranch} to origin in {repo}")
    try:
        git.push(f"-u origin {fullBranch}", execution_path=repo)
    except grape_errors.GrapeGitError as e:
        logging.error("{repo}:  {e.gitOutput}")


if __name__ == "__main__":
    from vine import grapeMenu
    menu = grapeMenu.menu()
    menu.applyMenuChoice("feature", [])
