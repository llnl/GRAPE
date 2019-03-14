import os
import option
import checkout
import utility
import grape_errors
import grapeGit as git
import grapeMenu
import config_parser_global
import multi_repo_cmd_launcher


class NewBranchOption(option.Option):
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
            grapeMenu.printMsg("WARNING: %s in .grapeconfig.flow.topicPrefixMappings should be lowercase." % topic)
            self._key = topic.lower()
        self._section = "Gitflow Tasks"
        self._public = public

    def description(self):
        return "Create and switch to a %s branch off of %s" % (self._key, self._public)



    def execute(self, args):
        start = args["--start"]
        if not start:
            start = self._public


        # decide whether to recurse
        recurse = config_parser_global.grapeConfig().get('workspace', 'manageSubmodules')
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


        branchName = self._key + "/" + args["--user"] + "/" + args["<descr>"]

        branchStatus = checkout.branchAlreadyExists(branchName)
        if branchStatus:
            grapeMenu.printMsg("Not creating new branch.")
            if branchStatus == 1:
                grapeMenu.printMsg("Use `grape checkout %s' instead." % branchName)
            return False

        activeSubmodulesCheck = git.getActiveSubmodules()

        addedModules = []
        removedModules = []
        changedURLModules = []
        if recurse:
            checkout.parseGitModulesDiffOutput(git.currentBranch(), start, addedModules, removedModules, changedURLModules)
            # deinit and clean out any submodules that changed urls or
            # are not present in the public branch.
            for sub in changedURLModules + removedModules:
                grapeMenu.printMsg("%s %s, attempting to remove references for %s submodule before branch creation." % (sub, "has changed URL" if sub in changedURLModules else "is not present in %s" % start, "active" if sub in activeSubmodulesCheck else "inactive"))
                cleaned = checkout.cleanSubmodule(sub, args, True, activeSubmodulesCheck)
                if not cleaned:
                    grapeMenu.printMsg("Failed to remove old submodule for %s." % sub)
                    return False

        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(createBranch,
                                                   runInSubmodules=recurse,
                                                   runInSubprojects=recurse,
                                                   runInOuter=True,
                                                   branch=start,
                                                   globalArgs=branchName)

        launcher.initializeCommands()
        grapeMenu.printMsg("About to create the following branches:")
        for repo, branch in zip(launcher.repos, launcher.branches):
            grapeMenu.printMsg("\t%s off of %s in %s" % (branchName, branch, repo))
        proceed = utility.userInput("Proceed? [y/n]", default="y")
        if proceed:
            grapeMenu.menu().applyMenuChoice('up', ['up', '--public=%s' % start])
            launcher.launchFromWorkspaceDir()
        else:
            grapeMenu.printMsg("branches not created")

        # reinit any submodules with changed URLs
        for sub in changedURLModules:
            if sub in activeSubmodulesCheck:
                os.chdir(utility.workspaceDir())
                git.submodule("update --init %s" % sub)
                os.chdir(os.path.join(utility.workspaceDir(), sub))
                # If there is already a branch by this name in the new repo,
                # this will reset the branch.
                git.checkout("-B %s" % branchName)

    def setDefaultConfig(self, config):
        config.ensureSection("workspace")
        config.set('workspace', 'manageSubmodules', 'True')
        config.set('workspace', 'submoduleTopicPrefixMappings', '?:develop')





class NewBranchOptionFactory():
    def __init__(self):
        pass

    @staticmethod
    def createNewBranchOptions(config):

        topicPublicMapping = config.getMapping('flow', 'topicPrefixMappings')
        options = []
        for topic in topicPublicMapping.keys():
            if topic != '?':
                options.append(NewBranchOption(topic, topicPublicMapping[topic]))
        return options




def createBranch(repo="unknown", branch="master", args=[]):
    branchPoint = branch
    fullBranch = args
    with utility.cd(repo):
        grapeMenu.printMsg("creating and switching to %s in %s" % (fullBranch, repo))
        try:
            git.checkout("-b %s %s " % (fullBranch, branchPoint))
        except grape_errors.GrapeGitError as e:
            print "%s:%s" % (repo, e.gitOutput)
            grapeMenu.printMsg("WARNING: %s in %s will not be pushed." % (fullBranch, repo))
            return
        grapeMenu.printMsg("pushing %s to origin in %s" % (fullBranch, repo))
        try:
            git.push("-u origin %s" % fullBranch)
        except grape_errors.GrapeGitError as e:
            print "%s:  %s" % (repo, e.gitOutput)
            return



if __name__ is "__main__":
    import grapeMenu
    menu = grapeMenu.menu()
    menu.applyMenuChoice("feature", [])
