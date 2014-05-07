import os

import option
import utility
import grapeGit as git
import grapeConfig


# update your custom sparse checkout view
class UpdateView(option.Option):
    """
    grape uv  - updates your active submodules.
    Usage: grape-uv [-f <sparsefile>]

    Options:
        
        -f                      Force removal of submodules currently in your view that are taken out of the view as a
                                result to this call to uv. (passes the -f flag to submodule deinit)

    """
    def __init__(self):
        super(UpdateView, self).__init__()
        self._key = "uv"
        self._section = "Workspace"

    def description(self):
        return "Update the view of your current working tree"

    @staticmethod
    def defineActiveSubmodules():
        allsubmodules = git.getAllSubmodules()
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
        base = git.baseDir()
        if base == "":
            return False

        included = self.defineActiveSubmodules()
        initStr = ""
        deinitStr = ""
        for submodule in included:
            if included[submodule]:
                initStr += ' %s' % submodule
            else:
                deinitStr += ' %s' % submodule

        #git.submodule("update --init %s" % initStr)
        git.submodule("init")
        os.chdir(git.baseDir())
        if deinitStr:
            git.submodule("deinit %s" % deinitStr.strip())
        git.submodule("update")

        # ensure submodule is on apppropriate branch
        config = grapeConfig.grapeConfig()
        if config.getboolean("workspace", "manageSubmodules"):
            publicBranches = config.getList("flow", "publicBranches")
            currentBranch = git.currentBranch()
            if currentBranch in publicBranches:
                desiredSubmoduleBranch = config.getMapping("workspace", "submodulepublicmappings")[currentBranch]
            else:
                desiredSubmoduleBranch = currentBranch
            for sub in git.getActiveSubmodules():
                self.safeSwitchHeadlessRepoToBranch(sub, desiredSubmoduleBranch)

        return True

    @staticmethod
    def safeSwitchHeadlessRepoToBranch(repo, branch):
        cwd = os.getcwd()
        os.chdir(os.path.join(git.baseDir(), repo))
        git.fetch()

        if git.currentBranch() == branch:
            os.chdir(cwd)
            return
        if git.hasBranch(branch):
            git.fetch("origin", "%s:%s" % (branch, branch))
            if git.SHA("HEAD") == git.SHA(branch):
                git.checkout(branch)
            else:
                utility.printMsg("WARNING: branch %s in submodule %s is not the same as HEAD. " % (branch, repo))
                valid = False
                while not valid:
                    method = utility.userInput("How do you want to check out %s? [f(orceToHead), k(eepAsIs)]" % branch,
                                               'k')
                    if method.lower() == 'k':
                        valid = True
                        git.checkout(branch)
                    elif method.lower() == 'f':
                        valid = True
                        git.checkout("-B %s" % branch)
                    else:
                        print "invalid input. Enter k or f. "

        else:
            utility.printMsg("submodule %s does not have branch %s. Creating it now. " % (repo, branch))
            git.checkout("-b %s" % branch)

        os.chdir(cwd)
        return

    def setDefaultConfig(self, config):
        config.ensureSection("workspace")
        config.set("workspace", "submodulepublicmappings", "?:master")
