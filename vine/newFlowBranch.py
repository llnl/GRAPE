import os
from grape.vine import checkout
from grape.vine import config_parser_global
from grape.vine import grape_errors
from grape.vine import grapeGit as git
from grape.vine import multi_repo_cmd_launcher
from grape.vine import utility
from grape.vine import vine_logging
from grape.vine.option import Option


class NewBranchOption(Option):
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
            vine_logging.printMsg(f"WARNING: {topic} in " +
                                  ".grapeconfig.flow.topicPrefixMappings " +
                                  "should be lowercase.")
            self._key = topic.lower()
        self._section = "Gitflow Tasks"
        self._public = public

    def description(self):
        return f"Create and switch to a {self._key} branch off of {self._public}"



    def execute(self, args):
        # Imported here to avoid circular dependencies
        from grape.vine import grapeMenu

        start = args["--start"]
        if not start:
            start = self._public


        # decide whether to recurse
        recurse = config_parser_global.grapeConfig().get(self.SECTION_WORKSPACE, 'manageSubmodules')
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


        branchName = os.path.join(self._key, args["--user"], args["<descr>"])

        branchStatus = checkout.branchAlreadyExists(branchName)
        if branchStatus:
            vine_logging.printMsg("Not creating new branch.")
            if branchStatus == 1:
                vine_logging.printMsg(f"Use `grape checkout {branchName}' " +
                                      "instead.")
            return False

        activeSubmodulesCheck = git.getActiveSubmodules(utility.workspaceDir())

        addedModules = []
        removedModules = []
        changedURLModules = []
        if recurse:
            checkout.parseGitModulesDiffOutput(git.currentBranch(), start, addedModules, removedModules, changedURLModules)
            # deinit and clean out any submodules that changed urls or
            # are not present in the public branch.
            for sub in changedURLModules + removedModules:
                url_update = "has changed URL" if sub in changedURLModules else f"is not present in {start}"
                maybe_active = "active" if sub in activeSubmodulesCheck else "inactive"
                vine_logging.printMsg(
                    f"{sub} {url_update}, attempting to remove references " +
                    f"for {maybe_active} submodule before branch creation.")
                cleaned = checkout.cleanSubmodule(sub, args, True, activeSubmodulesCheck)
                if not cleaned:
                    vine_logging.printMsg(
                        f"Failed to remove old submodule for {sub}.")
                    return False

        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(createBranch,
                                                   runInSubmodules=recurse,
                                                   runInSubprojects=recurse,
                                                   runInOuter=True,
                                                   branch=start,
                                                   globalArgs=branchName)

        launcher.initializeCommands()
        vine_logging.printMsg("About to create the following branches:")
        for repo, branch in zip(launcher.repos, launcher.branches):
            vine_logging.printMsg(
                f"\t{branchName} off of {branch} in {repo}")
        proceed = utility.userInput("Proceed? [y/n]", default="y")
        if proceed:
            grapeMenu.menu().applyMenuChoice('up', ['up', f'--public={start}'])
            launcher.launchFromWorkspaceDir()
        else:
            vine_logging.printMsg("branches not created")

        # reinit any submodules with changed URLs
        for sub in changedURLModules:
            if sub in activeSubmodulesCheck:
                os.chdir(utility.workspaceDir())
                git.submodule(f"update --init {sub}")
                os.chdir(os.path.join(utility.workspaceDir(), sub))
                # If there is already a branch by this name in the new repo,
                # this will reset the branch.
                git.checkout(f"-B {branchName}")

    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_WORKSPACE)
        config.set(self.SECTION_WORKSPACE, 'manageSubmodules', 'True')
        config.set(self.SECTION_WORKSPACE, 'submoduleTopicPrefixMappings', '?:develop')


class NewBranchOptionFactory(object):

    @staticmethod
    def createNewBranchOptions(config):
        topicPublicMapping = config.getMapping(Option.SECTION_FLOW, 'topicPrefixMappings')
        options = []
        for topic in topicPublicMapping.keys():
            if topic != '?':
                options.append(NewBranchOption(topic, topicPublicMapping[topic]))
        return options


def createBranch(repo="unknown", branch="master", args=[]):
    branchPoint = branch
    fullBranch = args
    with git.cd(repo):
        vine_logging.printMsg(f"creating and switching to {fullBranch} in {repo}")
        try:
            git.checkout(f"-b {fullBranch} {branchPoint} ")
        except grape_errors.GrapeGitError as e:
            print(f"{repo}:{e.gitOutput}")
            vine_logging.printMsg(f"WARNING: {fullBranch} in {repo}" +
                                  " will not be pushed.")
            return
        vine_logging.printMsg(f"pushing {fullBranch} to origin in {repo}")
        try:
            git.push(f"-u origin {fullBranch}")
        except grape_errors.GrapeGitError as e:
            print("{repo}:  {e.gitOutput}")
            return



if __name__ == "__main__":
    from grape.vine import grapeMenu
    menu = grapeMenu.menu()
    menu.applyMenuChoice("feature", [])
