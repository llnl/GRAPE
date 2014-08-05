import os

import option
import utility
import grapeGit as git
import grapeConfig
import checkout


# update your custom sparse checkout view
class UpdateView(option.Option):
    """
    grape uv  - updates your active submodules.
    Usage: grape-uv [-f <sparsefile>] [-v]

    Options:
        
        -f                      Force removal of submodules currently in your view that are taken out of the view as a
                                result to this call to uv. (passes the -f flag to submodule deinit)
        -v                      Be more verbose.

    """
    def __init__(self):
        super(UpdateView, self).__init__()
        self._key = "uv"
        self._section = "Workspace"

    def description(self):
        return "Update the view of your current working tree"

    @staticmethod
    def defineActiveSubmodules(quiet=False):
        allsubmodules = git.getAllSubmodules(quiet=quiet)
        toplevelDirs = {}
        toplevelSubs = []
        for sub in allsubmodules:
            prefix = git.branchPrefix(sub)
            if sub != prefix:
                toplevelDirs[prefix] = []
        for sub in allsubmodules:
            prefix = git.branchPrefix(sub)
            if sub != prefix:
                toplevelDirs[prefix].append(sub)
            else:
                toplevelSubs.append(sub)

        included = {}
        for directory in toplevelDirs:
            opt = utility.userInput("Would you like all, some, or none of the submodules in %s?" % directory,
                                    default="all")
            if opt.lower()[0] == "a":
                included[directory] = True
            if opt.lower()[0] == "n":
                included[directory] = False
            if opt.lower()[0] == "s":
                for submodule in toplevelDirs[directory]:
                    included[submodule] = utility.userInput("Would you like submodule %s? [y/n]" % submodule, 'n')
        for submodule in toplevelSubs:
            included[submodule] = utility.userInput("Would you like submodule %s? [y/n]" % submodule, 'n')
        return included

    def execute(self, args):
        quiet = not args["-v"]
        base = git.baseDir()
        if base == "":
            return False

        included = self.defineActiveSubmodules(quiet=quiet)
        initStr = ""
        if args["-f"]:
            deinitStr = "-f"
        else:
            deinitStr = ""
        for submodule in included:
            if included[submodule]:
                initStr += ' %s' % submodule
            else:
                deinitStr += ' %s' % submodule

        #git.submodule("update --init %s" % initStr)
        utility.printMsg("Configuring submodules...")
        git.submodule("init", quiet=quiet)
        os.chdir(git.baseDir())
        utility.printMsg("Initializing submodules...")
        if deinitStr:
            git.submodule("deinit %s" % deinitStr.strip(), quiet=quiet)
        git.submodule("update", quiet=quiet)

        # ensure submodule is on apppropriate branch
        config = grapeConfig.grapeConfig()
        if config.getboolean("workspace", "manageSubmodules"):
            publicBranches = config.getList("flow", "publicBranches")
            currentBranch = git.currentBranch()
            if currentBranch in publicBranches:
                desiredSubmoduleBranch = config.getMapping("workspace", "submodulepublicmappings")[currentBranch]
            else:
                desiredSubmoduleBranch = currentBranch
            utility.printMsg("Ensuring submodules are on %s branch..." % desiredSubmoduleBranch)
            for sub in git.getActiveSubmodules(quiet=quiet):
                self.safeSwitchHeadlessRepoToBranch(sub, desiredSubmoduleBranch, quiet)

        return True

    @staticmethod
    def safeSwitchHeadlessRepoToBranch(repo, branch, quiet):
        cwd = os.getcwd()
        os.chdir(os.path.join(git.baseDir(quiet=quiet), repo))
        git.fetch(quiet=quiet)

        if git.currentBranch() == branch:
            os.chdir(cwd)
            return

        if git.hasBranch(branch):
            git.fetch("origin", "%s:%s" % (branch, branch))

        checkout.Checkout.handledCheckout("-b", branch, repo, quiet=quiet)

        os.chdir(cwd)
        return

    def setDefaultConfig(self, config):
        config.ensureSection("workspace")
        config.set("workspace", "submodulepublicmappings", "?:master")
