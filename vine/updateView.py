import os
import shutil

import addSubproject
import option
import utility
import grapeGit as git
import grapeConfig
import grapeMenu
import checkout


# update your custom sparse checkout view
class UpdateView(option.Option):
    """
    grape uv  - Updates your active submodules and ensures you are on a consistent branch throughout your project.
    Usage: grape-uv [-f ] [-v] [--checkSubprojects] [-b] [--skipSubmodules] [--allSubmodules]
                    [--skipNestedSubprojects] [--allNestedSubprojects]

    Options:
        
        -f                      Force removal of subprojects currently in your view that are taken out of the view as a
                                result to this call to uv.
        -v                      Be more verbose.
        --checkSubprojects      Checks for branch model consistency across your submodules and subprojects, but does
                                not go through the 'which submodules do you want' script.
        -b                      Automatically creates subproject branches that should be there according to your branching
                                model. 
        --allSubmodules         Automatically add all submodules to your workspace. 
        --allNestedSubprojects  Automatically add all nested subprojects to your workspace. 

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
        for directory, subprojects in toplevelDirs.items():
            opt = utility.userInput("Would you like all, some, or none of the %ss in %s?" % (projectType,directory),
                                    default="all")
            if opt.lower()[0] == "a":
                for subproject in subprojects:
                    included[subproject] = True
                        
            if opt.lower()[0] == "n":
                for subproject in subprojects:
                    included[subproject] = False
            if opt.lower()[0] == "s":
                for subproject in subprojects: 
                    included[subproject] = utility.userInput("Would you like %s %s? [y/n]" % (projectType, subproject),
                                                            'n')
        for subprojects in toplevelSubs:
            included[subprojects] = utility.userInput("Would you like %s %s? [y/n]" % (projectType, subprojects), 'n')
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
        origwd = os.getcwd()
        os.chdir(utility.workspaceDir())
        base = git.baseDir()
        if base == "":
            return False
        hasSubmodules = len(git.getAllSubmodules()) > 0 and not args["--skipSubmodules"]
        if not args["--checkSubprojects"]:
            # handle submodules first
            if hasSubmodules:
                if args["--allSubmodules"]: 
                    includedSubmodules = {sub:True for sub in git.getAllSubmodules(quiet = quiet)}
                else:
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
                utility.printMsg("Initializing submodules...")
                git.submodule("init %s" % initStr.strip(), quiet=quiet)
                if deinitStr or deinitStr == "-f":
                    utility.printMsg("Deiniting submodules that were not requested... (%s)" % deinitStr)
                    git.submodule("deinit %s" % deinitStr.strip(), quiet=quiet)

                if initStr:
                    utility.printMsg("Updating active submodules...(%s)" % initStr)
                    git.submodule("update", quiet=quiet)

            # handle nested subprojects
            if not args["--skipNestedSubprojects"]: 
                
                nestedPrefixLookup = lambda x : config.get("nested-%s" % x, "prefix")
                allNestedSubprojects = config.getAllNestedSubprojects()
                if args["--allNestedSubprojects"]: 
                    includedNestedSubprojectPrefixes = {nestedPrefixLookup(sub):True for sub in allNestedSubprojects}
                else:
                    includedNestedSubprojectPrefixes = self.defineActiveNestedSubprojects(quiet=quiet)
                reverseLookupByPrefix = {nestedPrefixLookup(sub) : sub for sub in allNestedSubprojects} 
                userConfig = grapeConfig.grapeUserConfig()
                updatedActiveList = []
                for subproject, nowActive in includedNestedSubprojectPrefixes.items():
                    subprojectName = reverseLookupByPrefix[subproject]
                    section = "nested-%s" % reverseLookupByPrefix[subproject]
                    userConfig.ensureSection(section)
                    previouslyActive = userConfig.getboolean(section, "active")
                    previouslyActive = previouslyActive and os.path.exists(os.path.join(base, subproject))
                    userConfig.set(section, "active", "True" if previouslyActive else "False")
                    if nowActive and previouslyActive:
                        updatedActiveList.append(subprojectName)
    
                    if nowActive and not previouslyActive:
                        utility.printMsg("Activating Nested Subproject %s" % subproject)
                        addSubproject.AddSubproject.activateNestedSubproject(subprojectName, userConfig)
                        updatedActiveList.append(subprojectName)
    
                    if not nowActive and not previouslyActive:
                        pass
                    if not nowActive and previouslyActive:
                        #remove the subproject
                        subprojectdir = os.path.join(base, utility.makePathPortable(subproject))
                        proceed = args["-f"] or \
                                  utility.userInput("About to delete all contents in %s. Any uncommitted changes, committed changes "
                                                    "that have not been pushed, or ignored files will be lost.  Proceed?" %
                                                    subproject, 'n')
                        if proceed:
                            shutil.rmtree(subprojectdir)
                userConfig.setActiveNestedSubprojects(updatedActiveList)
                grapeConfig.writeConfig(userConfig, os.path.join(utility.workspaceDir(), ".git", ".grapeuserconfig"))

        checkoutArgs = "-b" if args["-b"] else ""

        if args["--checkSubprojects"]:
            utility.printMsg("Making sure all submodules are initialized...")
            git.submodule("init")
        for subproject in grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes():
            #ensure nested subprojects are on the appropriate branch (nested projects should have same branch layout)
            # as outer level repo. 
            desiredSubprojectBranch = git.currentBranch()
            utility.printMsg("Ensuring %s is on %s..." % (subproject, desiredSubprojectBranch))
            
            self.safeSwitchHeadlessRepoToBranch(subproject, desiredSubprojectBranch, checkoutArgs, quiet)


        # ensure submodule is on appropriate branch
        if config.getboolean("workspace", "manageSubmodules"):
            desiredSubmoduleBranch = self.getDesiredSubmoduleBranch(config)
            activeSubmodules = git.getActiveSubmodules(quiet=quiet)
            if activeSubmodules:
                utility.printMsg("Ensuring submodules are on %s branch..." % desiredSubmoduleBranch)
            for sub in activeSubmodules:
                utility.printMsg("Ensuring %s is on %s" % (sub, desiredSubmoduleBranch))
                self.safeSwitchHeadlessRepoToBranch(sub, desiredSubmoduleBranch, checkoutArgs, quiet)

        os.chdir(origwd)

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
    def safeSwitchHeadlessRepoToBranch(repo, branch, checkoutArgs, quiet):
        cwd = os.getcwd()
        os.chdir(os.path.join(git.baseDir(quiet=quiet), repo))
        git.fetch(quiet=quiet)

        if git.currentBranch() == branch:
            os.chdir(cwd)
            return

        if git.hasBranch(branch):
            try:
                git.fetch("origin", "%s:%s" % (branch, branch), quiet=quiet)
            except git.GrapeGitError as e:
                if "[rejected]" in e.gitOutput and "(non-fast-forward)" in e.gitOutput:
                    utility.printMsg("Fetch of %s rejected as non-fast-forward\nAttempting push of local %s in %s" % (branch, branch, repo))
                    try:
                        git.push("origin %s" % branch, quiet=quiet)
                    except git.GrapeGitError as e2:
                        utility.printMsg("Local and remote versions of %s may have diverged in %s" % (branch, repo))
                        utility.printMsg("%s" % e2.gitOutput)
                        mr = utility.userInput("Would you like to attempt to merge the remote using grape mr [y/n]", 'n')
                        if mr:
                            grapeMenu.menu().applyMenuChoice("mr", ["mr", branch])
                else:    
                    raise(e)

        checkout.Checkout.handledCheckout(checkoutArgs, branch, repo, quiet=quiet)

        os.chdir(cwd)
        return

    def setDefaultConfig(self, config):
        config.ensureSection("workspace")
        config.set("workspace", "submodulepublicmappings", "?:master")
