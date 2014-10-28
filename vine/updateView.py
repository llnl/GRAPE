import os
import shutil

import addSubproject
import option
import utility
import grapeGit as git
import grapeConfig
import checkout


# update your custom sparse checkout view
class UpdateView(option.Option):
    """
    grape uv  - Updates your active submodules and ensures you are on a consistent branch throughout your project.
    Usage: grape-uv [-f ] [-v] [--checkSubprojects]

    Options:
        
        -f                      Force removal of subprojects currently in your view that are taken out of the view as a
                                result to this call to uv.
        -v                      Be more verbose.
        --checkSubprojects      Checks for branch model consistency across your submodules and subprojects, but does
                                not go through the 'which submodules do you want' script.

    """
    def __init__(self):
        super(UpdateView, self).__init__()
        self._key = "uv"
        self._section = "Workspace"

    def description(self):
        return "Update the view of your current working tree"

    @staticmethod
    def defineActiveSubmodules(quiet=False, projectType="submodule"):
        """
        Queries the user for the submodules (projectType == "submodule") or nested subprojects
        (projectType == "nested subproject") they would like to activate.

        """
        if projectType == "submodule":
            allSubprojects = git.getAllSubmodules(quiet=quiet)

        if projectType == "nested subproject":
            config = grapeConfig.grapeConfig()
            allSubprojectNames = config.getAllNestedSubprojects()
            allSubprojects = []
            for project in allSubprojectNames:
                allSubprojects.append(config.get("nested-%s" % project, "prefix"))

        toplevelDirs = {}
        toplevelSubs = []
        for sub in allSubprojects:
            # we are taking advantage of the fact that branchPrefixes are the same as directory prefixes for local
            # top-level dirs.
            prefix = git.branchPrefix(sub)
            if sub != prefix:
                toplevelDirs[prefix] = []
        for sub in allSubprojects:
            prefix = git.branchPrefix(sub)
            if sub != prefix:
                toplevelDirs[prefix].append(sub)
            else:
                toplevelSubs.append(sub)

        included = {}
        for directory in toplevelDirs:
            opt = utility.userInput("Would you like all, some, or none of the %ss in %s?" % (projectType,directory),
                                    default="all")
            if opt.lower()[0] == "a":
                included[directory] = True
            if opt.lower()[0] == "n":
                included[directory] = False
            if opt.lower()[0] == "s":
                for submodule in toplevelDirs[directory]:
                    included[submodule] = utility.userInput("Would you like %s %s? [y/n]" % (projectType, submodule),
                                                            'n')
        for submodule in toplevelSubs:
            included[submodule] = utility.userInput("Would you like %s %s? [y/n]" % (projectType, submodule), 'n')
        return included

    @staticmethod
    def defineActiveNestedSubprojects(quiet=False):
        """
        Queries the user for the nested subprojects they would like to activate.

        """
        return UpdateView.defineActiveSubmodules(quiet=quiet, projectType="nested subproject")

    def execute(self, args):
        config = grapeConfig.grapeConfig()
        quiet = not args["-v"]
        base = git.baseDir()
        if base == "":
            return False
        if not args["--checkSubprojects"]:
            # handle submodules first
            includedSubmodules = self.defineActiveSubmodules(quiet=quiet)
            initStr = ""
            if args["-f"]:
                deinitStr = "-f"
            else:
                deinitStr = ""
            for submodule, nowActive in includedSubmodules.items():
                if nowActive:
                    initStr += ' %s' % submodule
                else:
                    deinitStr += ' %s' % submodule

            utility.printMsg("Configuring submodules...")
            git.submodule("init", quiet=quiet)
            os.chdir(git.baseDir())
            utility.printMsg("Initializing submodules...")
            if deinitStr or deinitStr == "-f":
                utility.printMsg("Deiniting submodules that were not requested... (%s)" % deinitStr)
                git.submodule("deinit %s" % deinitStr.strip(), quiet=quiet)

            if initStr:
                utility.printMsg("Updating active submodules...(%s)" % initStr)
                git.submodule("update", quiet=quiet)

            # handle nested subprojects
            os.chdir(base)
            includedNestedSubprojectPrefices = self.defineActiveNestedSubprojects(quiet=quiet)

            allNestedSubprojects = config.getAllNestedSubprojects()
            reverseLookupByPrefix = {}
            for sub in allNestedSubprojects:
                reverseLookupByPrefix[config.get("nested-%s" % sub, "prefix")] = sub

            userConfig = grapeConfig.grapeUserConfig()
            for subproject, nowActive in includedNestedSubprojectPrefices.items():
                previouslyActive = userConfig.get("nested-%s" % reverseLookupByPrefix[subproject])
                if nowActive and previouslyActive:
                    pass
                if nowActive and not previouslyActive:
                    utility.printMsg("Activating Nested Subproject %s" % subproject)
                    addSubproject.AddSubproject.activateNestedSubproject(reverseLookupByPrefix[subproject], userConfig)
                    grapeConfig.writeConfig(userConfig, os.path.join(base, ".grapeuserconfig"))
                if not nowActive and not previouslyActive:
                    pass
                if not nowActive and previouslyActive:
                    #remove the submodule
                    subprojectdir = os.path.join(base, utility.makePathPortable(subproject))
                    os.chdir(subprojectdir)
                    proceed = args["-f"] or \
                              utility.userInput("About to delete all contents in %s. Any uncommitted changes, branches "
                                                "that are not pushed, or ignored files will be removed.  Proceed?" %
                                                subproject, 'n')
                    if proceed:
                        shutil.rmtree(subprojectdir)

        for subproject in grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojects():
            #ensure nested subprojects are on the appropriate branch
            desiredSubprojectBranch = self.getDesiredSubmoduleBranch(config)
            utility.printMsg("Ensuring %s is on %s..." % (subproject, desiredSubprojectBranch))
            self.safeSwitchHeadlessRepoToBranch(subproject, desiredSubprojectBranch, quiet)


        # ensure submodule is on apppropriate branch
        if config.getboolean("workspace", "manageSubmodules"):
            desiredSubmoduleBranch = self.getDesiredSubmoduleBranch(config)
            utility.printMsg("Ensuring submodules are on %s branch..." % desiredSubmoduleBranch)
            for sub in git.getActiveSubmodules(quiet=quiet):
                utility.printMsg("Ensuring %s is on %s" % (sub, desiredSubmoduleBranch))
                self.safeSwitchHeadlessRepoToBranch(sub, desiredSubmoduleBranch, quiet)

        #ensure nested subprojects are on the appropriate branch

        return True

    @staticmethod
    def getDesiredSubmoduleBranch(config):
        publicBranches = config.getList("flow", "publicBranches")
        currentBranch = git.currentBranch()
        if currentBranch in publicBranches:
            desiredSubmoduleBranch = config.getMapping("workspace", "submodulepublicmappings")[currentBranch]
        else:
            desiredSubmoduleBranch = currentBranch
        return desiredSubmoduleBranch


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

        checkout.Checkout.handledCheckout("-b", branch, repo)

        os.chdir(cwd)
        return

    def setDefaultConfig(self, config):
        config.ensureSection("workspace")
        config.set("workspace", "submodulepublicmappings", "?:master")
