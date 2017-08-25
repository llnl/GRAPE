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
    Usage: grape-uv [-f ] [--checkSubprojects] [-b] [--skipSubmodules] [--allSubmodules]
                    [--skipNestedSubprojects] [--allNestedSubprojects] [--sync=<bool>]
                    [--add=<addedSubmoduleOrSubproject>...] [--rm=<removedSubmoduleOrSubproject>...]

    Options:
        -f                      Force removal of subprojects currently in your view that are taken out of the view as a
                                result to this call to uv.
        --checkSubprojects      Checks for branch model consistency across your submodules and subprojects, but does
                                not go through the 'which submodules do you want' script.
        -b                      Automatically creates subproject branches that should be there according to your branching
                                model. 
        --allSubmodules         Automatically add all submodules to your workspace. 
        --allNestedSubprojects  Automatically add all nested subprojects to your workspace.
        --sync=<bool>           Take extra steps to ensure the branch you're on is up to date with origin,
                                either by pushing or pulling the remote tracking branch.
                                This will also checkout the public branch in a headless state prior to offering to create
                                a new branch (in repositories where the current branch does not exist).
                                [default: .grapeconfig.post-checkout.syncWithOrigin]
        --add=<project>         Submodule or subproject to add to the workspace. Can be defined multiple times. 
        --remove=<project>      Submodule or subproject to remove from the workspace. Can be defined multiple times.

    """
    def __init__(self):
        super(UpdateView, self).__init__()
        self._key = "uv"
        self._section = "Workspace"
        self._pushBranch = False
        self._skipPush = False

    def description(self):
        return "Update the view of your current working tree"

    @staticmethod
    def defineActiveSubmodules(projectType="submodule"):
        """
        Queries the user for the submodules (projectType == "submodule") or nested subprojects
        (projectType == "nested subproject") they would like to activate.

        """
        if projectType == "submodule":
            allSubprojects = git.getAllSubmodules()
            activeSubprojects = git.getActiveSubmodules()

        if projectType == "nested subproject":
            config = grapeConfig.grapeConfig()
            allSubprojectNames = config.getAllNestedSubprojects()
            allSubprojects = []
            for project in allSubprojectNames:
                allSubprojects.append(config.get("nested-%s" % project, "prefix"))
            activeSubprojects = grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes()

        toplevelDirs = {}
        toplevelActiveDirs = {}
        toplevelSubs = []
        for sub in allSubprojects:
            # we are taking advantage of the fact that branchPrefixes are the same as directory prefixes for local
            # top-level dirs.
            prefix = git.branchPrefix(sub)
            if sub != prefix:
                toplevelDirs[prefix] = []
                toplevelActiveDirs[prefix] = []
        for sub in allSubprojects:
            prefix = git.branchPrefix(sub)
            if sub != prefix:
                toplevelDirs[prefix].append(sub)
            else:
                toplevelSubs.append(sub)
        for sub in activeSubprojects:
            prefix = git.branchPrefix(sub)
            if sub != prefix:
                toplevelActiveDirs[prefix].append(sub)

        included = {}
        for directory, subprojects in toplevelDirs.items():

            activeDir = toplevelActiveDirs[directory]
            if len(activeDir) == 0:
                defaultValue = "none"
            elif set(activeDir) == set(subprojects):
                defaultValue = "all"
            else:
                defaultValue = "some"

            opt = utility.userInput("Would you like all, some, or none of the %ss in %s?" % (projectType,directory),
                                    default=defaultValue)
            if opt.lower()[0] == "a":
                for subproject in subprojects:
                    included[subproject] = True
                        
            if opt.lower()[0] == "n":
                for subproject in subprojects:
                    included[subproject] = False
            if opt.lower()[0] == "s":
                for subproject in subprojects: 
                    included[subproject] = utility.userInput("Would you like %s %s? [y/n]" % (projectType, subproject),
                                                             'y' if (subproject in activeSubprojects) else 'n')
        for subproject in toplevelSubs:
            included[subproject] = utility.userInput("Would you like %s %s? [y/n]" % (projectType, subproject),
                                                     'y' if (subproject in activeSubprojects) else 'n')
        return included

    @staticmethod
    def defineActiveNestedSubprojects():
        """
        Queries the user for the nested subprojects they would like to activate.

        """
        return UpdateView.defineActiveSubmodules(projectType="nested subproject")

    def execute(self, args):
        sync = args["--sync"].lower().strip()
        sync = sync == "true" or sync == "yes"
        args["--sync"] = sync
        config = grapeConfig.grapeConfig()
        origwd = os.getcwd()
        wsDir = utility.workspaceDir()
        os.chdir(wsDir)
        base = git.baseDir()
        if base == "":
            return False
        hasSubmodules = len(git.getAllSubmodules()) > 0 and not args["--skipSubmodules"]
        includedSubmodules = {}
        includedNestedSubprojectPrefixes = {}

        allSubmodules = git.getAllSubmodules()
        allNestedSubprojects = config.getAllNestedSubprojects()
        
        addedSubmodules = [] 
        addedNestedSubprojects = [] 
        addedProjects = args["--add"]
        notFound = []
       
        for proj in addedProjects:
            if proj in allSubmodules:
                addedSubmodules.append(proj)
            elif proj in allNestedSubprojects:
                addedNestedSubprojects.append(proj)
            else:
                notFound.append(proj)
        
        rmSubmodules = []
        rmNestedSubprojects = []
        rmProjects = args["--rm"]
        
        for proj in rmProjects:
            if proj in allSubmodules:
                rmSubmodules.append(proj)
            elif proj in allNestedSubprojects:
                rmNestedSubprojects.append(proj)
            else:
                notFound.append(proj)

        if notFound:
            utility.printMsg("\"%s\" not found in submodules %s \nor\n nested subprojects %s" % (",".join(notFound),",".join(allSubmodules),",".join(allNestedSubprojects)))
            return False
                
       
        if not args["--checkSubprojects"]:
            # get submodules to update
            if hasSubmodules:
                if args["--allSubmodules"]: 
                    includedSubmodules = {sub:True for sub in allSubmodules}
                elif args["--add"] or args["--rm"]:
                    includedSubmodules = {sub:True for sub in git.getActiveSubmodules()}
                    includedSubmodules.update({sub:True for sub in addedSubmodules})
                    includedSubmodules.update({sub:False for sub in rmSubmodules})
                else:
                    includedSubmodules = self.defineActiveSubmodules()

            # get subprojects to update
            if not args["--skipNestedSubprojects"]: 
                
                nestedPrefixLookup = lambda x : config.get("nested-%s" % x, "prefix")
                if args["--allNestedSubprojects"]: 
                    includedNestedSubprojectPrefixes = {nestedPrefixLookup(sub):True for sub in allNestedSubprojects}
                elif args["--add"] or args["--rm"]:
                    includedNestedSubprojectPrefixes = {sub:True for sub in grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes()}
                    includedNestedSubprojectPrefixes.update({nestedPrefixLookup(sub):True for sub in addedNestedSubprojects})
                    includedNestedSubprojectPrefixes.update({nestedPrefixLookup(sub):False for sub in rmNestedSubprojects})
                else:
                    includedNestedSubprojectPrefixes = self.defineActiveNestedSubprojects()                    
            
            if hasSubmodules:
                initStr = ""
                deinitStr = ""
                rmCachedStr = ""
                resetStr = ""
                for submodule, nowActive in includedSubmodules.items():
                    if nowActive:
                        initStr += ' %s' % submodule
                    else:
                        deinitStr += ' %s' % submodule
                        rmCachedStr += ' %s' % submodule
                        resetStr += ' %s' % submodule
                if args["-f"] and deinitStr:
                    deinitStr = "-f"+deinitStr

                utility.printMsg("Configuring submodules...")
                utility.printMsg("Initializing submodules...")
                git.submodule("init %s" % initStr.strip())
                if deinitStr:
                    utility.printMsg("Deiniting submodules that were not requested... (%s)" % deinitStr)
                    done = False
                    while not done:
                        try:
                            git.submodule("deinit %s" % deinitStr.strip())
                            done = True
                        except git.GrapeGitError as e:
                            if "the following file has local modifications" in e.gitOutput:
                                print e.gitOutput
                                utility.printMsg("A submodule that you wanted to remove has local modifications. "
                                                 "Use grape uv -f to force removal.")
                                return False
                            
                            elif "use 'rm -rf' if you really want to remove it including all of its history" in e.gitOutput:
                                if not args["-f"]:
                                    raise e
                                # it is safe to move the .git of the submodule to the .git/modules area of the workspace...
                                module = None
                                for l in e.gitOutput.split('\n'):
                                    if "Submodule work tree" in l and "contains a .git directory" in l:
                                        module = l.split("'")[1]
                                        break
                                if module:
                                    src = os.path.join(module, ".git")
                                    dest =  os.path.join(wsDir, ".git", "modules", module)
                                    utility.printMsg("Moving %s to %s"%(src, dest))
                                    shutil.move(src, dest )
                                else:
                                    raise e
                            else:
                                raise e
                    git.rm("--cached %s" % rmCachedStr)
                    git.reset(" %s" % resetStr)

                if initStr:
                    utility.printMsg("Updating active submodules...(%s)" % initStr)
                    git.submodule("update")

            # handle nested subprojects
            if not args["--skipNestedSubprojects"]: 
                reverseLookupByPrefix = {nestedPrefixLookup(sub) : sub for sub in allNestedSubprojects} 
                userConfig = grapeConfig.grapeUserConfig()
                updatedActiveList = []
                for subproject, nowActive in includedNestedSubprojectPrefixes.items():
                    subprojectName = reverseLookupByPrefix[subproject]
                    section = "nested-%s" % reverseLookupByPrefix[subproject]
                    userConfig.ensureSection(section)
                    previouslyActive = userConfig.getboolean(section, "active")
                    previouslyActive = previouslyActive and os.path.exists(os.path.join(base, subproject, ".git"))
                    userConfig.set(section, "active", "True" if previouslyActive else "False")
                    if nowActive and previouslyActive:
                        updatedActiveList.append(subprojectName)
    
                    if nowActive and not previouslyActive:
                        utility.printMsg("Activating Nested Subproject %s" % subproject)
                        if not addSubproject.AddSubproject.activateNestedSubproject(subprojectName, userConfig):
                            utility.printMsg("Can't activate %s. Exiting..." % subprojectName)
                            return False
                        
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

        safeSwitchWorkspaceToBranch( git.currentBranch(), checkoutArgs, sync)

        os.chdir(origwd)

        return True

    @staticmethod
    def getDesiredSubmoduleBranch(config):
        publicBranches = config.getPublicBranchList()
        currentBranch = git.currentBranch()
        if currentBranch in publicBranches:
            desiredSubmoduleBranch = config.getMapping("workspace", "submodulepublicmappings")[currentBranch]
        else:
            desiredSubmoduleBranch = currentBranch
        return desiredSubmoduleBranch


    def setDefaultConfig(self, config):
        config.ensureSection("workspace")
        config.set("workspace", "submodulepublicmappings", "?:master")
       


def ensureLocalUpToDateWithRemote(repo = '', branch = 'master'):
    utility.printMsg( "Ensuring local branch %s in %s is up to date with origin" % (branch, repo))
    with utility.cd(repo):
        # attempt to fetch the requested branch
        try:
            git.fetch("origin", "%s:%s" % (branch, branch))
        except:
            # the branch may not exist, but this is ok
            pass
        
        if git.currentBranch() == branch:
            return

        if not git.hasBranch(branch):
            # switch to corresponding public branch if the branch does not exist
            public = grapeConfig.workspaceConfig().getPublicBranchFor(branch)
            # figure out if this is a submodule
            relpath = os.path.relpath(repo, utility.workspaceDir())
            relpath = relpath.replace('\\',"/")
            with utility.cd(utility.workspaceDir()):
                # if this is a submodule, get the appropriate public mapping
                if relpath in git.getAllSubmoduleURLMap().keys():
                    public = grapeConfig.workspaceConfig().getMapping("workspace", "submodulepublicmappings")[public]
            utility.printMsg("Branch %s does not exist in %s, switching to %s and detaching" % (branch, repo, public))
            git.checkout(public)
            git.pull("origin %s" % (public))
            git.checkout("--detach HEAD")

def cleanupPush(repo='', branch='', args='none'):
    with utility.cd(repo):
        utility.printMsg("Attempting push of local %s in %s" % (branch, repo))
        git.push("origin %s" % branch)                           


def handleCleanupPushMRE(mre):
    for e, repo, branch in zip(mre.exceptions(), mre.repos(), mre.branches()):
        try:
            raise e
        except git.GrapeGitError as e2:
            utility.printMsg("Local and remote versions of %s may have diverged in %s" % (branch, repo))
            utility.printMsg("%s" % e2.gitOutput)
            utility.printMsg("Use grape pull to merge the remote version into the local version.")    

def handleEnsureLocalUpToDateMRE(mre):
    _pushBranch = False
    _skipPush = False
    cleanupPushArgs = []
    for e1, repo, branch in zip(mre.exceptions(), mre.repos(), mre.branches()):
        try: 
            raise e1
        except git.GrapeGitError as e:
            if ("[rejected]" in e.gitOutput and "(non-fast-forward)" in e.gitOutput) or "Couldn't find remote ref" in e.gitOutput:
                if "Couldn't find remote ref" in e.gitOutput:
                    if not _pushBranch:
                        utility.printMsg("No remote reference to %s in %s's origin. You may want to push this branch." % (branch, repo))
                else:
                    utility.printMsg("Fetch of %s rejected as non-fast-forward in repo %s" % (branch, repo))
                pushBranch = _pushBranch
                if _skipPush:
                    pushBranch = False
                elif not pushBranch:
                    pushBranch =  utility.userInput("Would you like to push your local branch? \n"
                                                    "(select 'a' to say yes for (a)ll subprojects, 's' to (s)kip push for all subprojects)"
                                                    "\n(y,n,a,s)", 'y')
                    
                if str(pushBranch).lower()[0] == 'a':
                    _pushBranch = True
                    pushBranch = True
                if str(pushBranch).lower()[0] == 's':
                    _skipPush = True
                    pushBranch = False
                if pushBranch:
                    
                    cleanupPushArgs.append((repo, branch, None))
                else:
                    utility.printMsg("Skipping push of local %s in %s" % (branch, repo))
                    
            elif e.commError:
                utility.printMsg("Could not update %s from origin due to a connectivity issue. Checking out most recent\n"
                                 "local version. " % branch)
            else:    
                raise(e)
   
    # do another MRC launch to do any follow up pushes that were requested. 
    utility.MultiRepoCommandLauncher(cleanupPush, listOfRepoBranchArgTuples=cleanupPushArgs).launchFromWorkspaceDir(handleMRE=handleCleanupPushMRE)
    return

def safeSwitchWorkspaceToBranch(branch, checkoutArgs, sync):
    # Ensure local branches that you are about to check out are up to date with the remote
    if sync:
        launcher = utility.MultiRepoCommandLauncher(ensureLocalUpToDateWithRemote, branch = branch, globalArgs=[checkoutArgs])
        launcher.launchFromWorkspaceDir(handleMRE=handleEnsureLocalUpToDateMRE)
    # Do a checkout
    # Pass False instead of sync since if sync is True ensureLocalUpToDateWithRemote will have already performed the fetch
    launcher = utility.MultiRepoCommandLauncher(checkout.handledCheckout, branch = branch, globalArgs = [checkoutArgs, False])
    launcher.launchFromWorkspaceDir(handleMRE=checkout.handleCheckoutMRE)

    return
