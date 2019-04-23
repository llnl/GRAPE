import os
import shutil
from grape.vine import addSubproject
from grape.vine import checkout
from grape.vine import config_parser_global
from grape.vine import config_parser_user
from grape.vine import config_parser_workspace
from grape.vine import grape_errors
from grape.vine import grapeGit as git
from grape.vine import multi_repo_cmd_launcher
from grape.vine import utility
from grape.vine import vine_logging
from grape.vine.option import Option

try:
    import Tkinter as Tk
    TkinterImportError = None
except ImportError as e:
    TkinterImportError = e


# update your custom sparse checkout view
class UpdateView(Option):
    """
    grape uv  - Updates your active submodules and ensures you are on a consistent branch throughout your project.
    Usage: grape-uv [-f] [--checkSubprojects] [-b] [--skipSubmodules] [--allSubmodules] [--gui]
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
        --gui                   Use the graphical user interface to select your view.
    """
    def __init__(self):
        super(UpdateView, self).__init__()
        self._key = "uv"
        self._section = "Workspace"
        self._pushBranch = False
        self._skipPush = False
        self.uvManager = None

    def description(self):
        return "Update the view of your current working tree"

    def defineActiveSubprojects(self, projectType="submodule"):
        """
        Queries the user for the submodules (projectType == "submodule") or nested subprojects
        (projectType == "nested subproject") they would like to activate.

        """
        if projectType == "submodule":
            allSubprojects = git.getAllSubmodules()
            activeSubprojects = git.getActiveSubmodules(utility.workspaceDir())

        if projectType == "nested subproject":
            config = config_parser_global.grapeConfig()
            allSubprojectNames = config.getAllNestedSubprojects()
            allSubprojects = []
            for project in allSubprojectNames:
                allSubprojects.append(config.get(f"nested-{project}", "prefix"))
            activeSubprojects = config_parser_user.getAllActiveNestedSubprojectPrefixes()

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

        if self.uvManager:
            self.uvManager.createFrame(projectType)

        for directory, subprojects in toplevelDirs.items():

            activeDir = toplevelActiveDirs[directory]
            if len(activeDir) == 0:
                defaultValue = "none"
            elif set(activeDir) == set(subprojects):
                defaultValue = "all"
            else:
                defaultValue = "some"

            if self.uvManager:
                opt = "s"
                self.uvManager.createSection(directory)
            else:
                opt = utility.userInput(f"Would you like all, some, or none of the {projectType}s in {directory}?",
                                        default=defaultValue)

            if opt.lower()[0] == "a":
                for subproject in subprojects:
                    included[subproject] = True

            if opt.lower()[0] == "n":
                for subproject in subprojects:
                    included[subproject] = False
            if opt.lower()[0] == "s":
                for subproject in sorted(subprojects, key=lambda v: (v.upper(), v[0].islower())):
                    if self.uvManager:
                        # Set the default value for the gui
                        subIsActive = subproject in activeSubprojects
                        included[subproject] = subIsActive
                        self.uvManager.createEntry(subproject, subIsActive)
                    else:
                        included[subproject] = utility.userInput(f"Would you like {projectType} {subproject}? [y/n]",
                                                                 'y' if (subproject in activeSubprojects) else 'n')
        if self.uvManager and toplevelSubs:
            self.uvManager.createSection("top level")
        for subproject in sorted(toplevelSubs, key=lambda v: (v.upper(), v[0].islower())):
            if self.uvManager:
                # Set the default value for the gui
                subIsActive = subproject in activeSubprojects
                included[subproject] = subIsActive
                self.uvManager.createEntry(subproject, subIsActive)
            else:
                included[subproject] = utility.userInput(f"Would you like {projectType} {subproject}? [y/n]",
                                                         'y' if (subproject in activeSubprojects) else 'n')
        return included

    def defineActiveNestedSubprojects(self):
        """
        Queries the user for the nested subprojects they would like to activate.

        """
        return self.defineActiveSubprojects(projectType="nested subproject")

    def execute(self, args):
        if args["--gui"] and TkinterImportError:
            vine_logging.printMsg("grape uv --gui requires Tkinter.\n  The following error was raised during the import:\n\n%s\n" % TkinterImportError)
            return True
        sync = args["--sync"].lower().strip()
        sync = sync == "true" or sync == "yes"
        args["--sync"] = sync
        config = config_parser_global.grapeConfig()
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
            vine_logging.printMsg(f"\"{','.join(notFound)}\" not found in submodules {','.join(allSubmodules)} \nor\n nested subprojects {','.join(allNestedSubprojects)}")
            return False

        if not args["--checkSubprojects"]:
            root = None
            if args["--gui"]:
                root = Tk.Tk()
                root.title("GRAPE uv - select active subprojects")
                self.uvManager = UVManager(master=root)

            # get submodules to update
            if hasSubmodules:
                if args["--allSubmodules"]:
                    includedSubmodules = {sub:True for sub in allSubmodules}
                elif args["--add"] or args["--rm"]:
                    includedSubmodules = {sub:True for sub in git.getActiveSubmodules(utility.workspaceDir())}
                    includedSubmodules.update({sub:True for sub in addedSubmodules})
                    includedSubmodules.update({sub:False for sub in rmSubmodules})
                else:
                    includedSubmodules = self.defineActiveSubprojects()

            # get subprojects to update
            if not args["--skipNestedSubprojects"]:

                nestedPrefixLookup = lambda x : config.get(f"nested-{x}", "prefix")
                if args["--allNestedSubprojects"]:
                    includedNestedSubprojectPrefixes = {nestedPrefixLookup(sub):True for sub in allNestedSubprojects}
                elif args["--add"] or args["--rm"]:
                    includedNestedSubprojectPrefixes = {sub:True for sub in config_parser_user.getAllActiveNestedSubprojectPrefixes()}
                    includedNestedSubprojectPrefixes.update({nestedPrefixLookup(sub):True for sub in addedNestedSubprojects})
                    includedNestedSubprojectPrefixes.update({nestedPrefixLookup(sub):False for sub in rmNestedSubprojects})
                else:
                    includedNestedSubprojectPrefixes = self.defineActiveNestedSubprojects()

            if root:
                self.uvManager.finalize()
                root.mainloop()
                if self.uvManager.saved == False:
                    vine_logging.printMsg("Not changing working view.")
                    return False
                # If --all/--add/--rm is used, only consider the
                # command line for the included subprojects.
                if self.uvManager.includedSubmodules == None:
                    vine_logging.printMsg("Submodule changes from GUI ignored")
                else:
                    includedSubmodules = self.uvManager.includedSubmodules
                if self.uvManager.includedNestedSubprojects == None:
                    vine_logging.printMsg("Nested subproject changes from GUI ignored")
                else:
                    includedNestedSubprojectPrefixes = self.uvManager.includedNestedSubprojects
                try:
                    root.destroy()
                except:
                    pass

            if hasSubmodules:
                initStr = ""
                deinitStr = ""
                rmCachedStr = ""
                resetStr = ""
                for submodule, nowActive in includedSubmodules.items():
                    if nowActive:
                        initStr += f' {submodule}'
                    else:
                        deinitStr += f' {submodule}'
                        rmCachedStr += f' {submodule}'
                        resetStr += f' {submodule}'
                if args["-f"] and deinitStr:
                    deinitStr = "-f"+deinitStr

                vine_logging.printMsg("Configuring submodules...")
                vine_logging.printMsg("Initializing submodules...")
                git.submodule(f"init {initStr.strip()}")
                if deinitStr:
                    vine_logging.printMsg(f"Deiniting submodules that were not requested... ({deinitStr})")
                    done = False
                    while not done:
                        try:
                            git.submodule(f"deinit {deinitStr.strip()}")
                            done = True
                        except grape_errors.GrapeGitError as e:
                            if "the following file has local modifications" in e.gitOutput:
                                print(e.gitOutput)
                                vine_logging.printMsg("A submodule that you wanted to remove has local modifications. "
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
                                    vine_logging.printMsg(f"Moving {src} to {dest}")
                                    shutil.move(src, dest )
                                else:
                                    raise e
                            else:
                                raise e
                    git.rm(f"--cached {rmCachedStr}")
                    git.reset(f" {resetStr}")

                if initStr:
                    vine_logging.printMsg(f"Updating active submodules...({initStr})")
                    git.submodule("update")

            # handle nested subprojects
            if not args["--skipNestedSubprojects"]:
                reverseLookupByPrefix = {nestedPrefixLookup(sub) : sub for sub in allNestedSubprojects}
                userConfig = config_parser_user.GrapeConfigParserUser()
                updatedActiveList = []
                for subproject, nowActive in includedNestedSubprojectPrefixes.items():
                    subprojectName = reverseLookupByPrefix[subproject]
                    section = f"nested-{reverseLookupByPrefix[subproject]}"
                    userConfig.ensureSection(section)
                    previouslyActive = userConfig.getboolean(section, "active")
                    previouslyActive = previouslyActive and os.path.exists(os.path.join(base, subproject, ".git"))
                    userConfig.set(section, "active", "True" if previouslyActive else "False")
                    if nowActive and previouslyActive:
                        updatedActiveList.append(subprojectName)

                    if nowActive and not previouslyActive:
                        vine_logging.printMsg(f"Activating Nested Subproject {subproject}")
                        if not addSubproject.AddSubproject.activateNestedSubproject(subprojectName, userConfig):
                            vine_logging.printMsg(f"Can't activate {subprojectName}. Exiting...")
                            return False

                        updatedActiveList.append(subprojectName)

                    if not nowActive and not previouslyActive:
                        pass
                    if not nowActive and previouslyActive:
                        #remove the subproject
                        subprojectdir = os.path.join(base, git.makePathPortable(subproject))
                        proceed = args["-f"] or \
                                  utility.userInput(f"About to delete all contents in {subproject}. " +
                                                    "Any uncommitted changes, committed changes that have " +
                                                    "not been pushed, or ignored files will be lost.  Proceed?", 'n')
                        if proceed:
                            shutil.rmtree(subprojectdir)
                userConfig.setActiveNestedSubprojects(updatedActiveList)
                config_parser_global.writeConfig(userConfig, os.path.join(utility.workspaceDir(), ".git", ".grapeuserconfig"))

        checkoutArgs = "-b" if args["-b"] else ""

        safeSwitchWorkspaceToBranch( git.currentBranch(), checkoutArgs, sync)

        os.chdir(origwd)

        return True

    @staticmethod
    def getDesiredSubmoduleBranch(config):
        publicBranches = config.getPublicBranchList()
        currentBranch = git.currentBranch()
        if currentBranch in publicBranches:
            desiredSubmoduleBranch = config.getMapping(Option.SECTION_WORKSPACE, "submodulepublicmappings")[currentBranch]
        else:
            desiredSubmoduleBranch = currentBranch
        return desiredSubmoduleBranch


    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_WORKSPACE)
        config.set(self.SECTION_WORKSPACE, "submodulepublicmappings", "?:master")



def ensureLocalUpToDateWithRemote(repo = '', branch = 'master'):
    vine_logging.printMsg(f"Ensuring local branch {branch} in {repo} is up to date with origin")
    with utility.cd(repo):
        # attempt to fetch the requested branch
        try:
            git.fetch("origin", f"{branch}:{branch}")
        except:
            # the branch may not exist, but this is ok
            pass

        if git.currentBranch() == branch:
            return

        if not git.hasBranch(branch):
            # switch to corresponding public branch if the branch does not exist
            public = config_parser_workspace.GrapeConfigParserWorkspace().getPublicBranchFor(branch)
            # figure out if this is a submodule
            relpath = os.path.relpath(repo, utility.workspaceDir())
            relpath = relpath.replace('\\',"/")
            with utility.cd(utility.workspaceDir()):
                # if this is a submodule, get the appropriate public mapping
                if relpath in git.getAllSubmoduleURLMap().keys():
                    public = config_parser_workspace.GrapeConfigParserWorkspace().getMapping(Option.SECTION_WORKSPACE, "submodulepublicmappings")[public]
            vine_logging.printMsg(f"Branch {branch} does not exist in {repo}, switching to {public} and detaching")
            git.checkout(public)
            git.pull(f"origin {public}")
            git.checkout("--detach HEAD")

def cleanupPush(repo='', branch='', args='none'):
    with utility.cd(repo):
        vine_logging.printMsg(f"Attempting push of local {branch} in {repo}")
        git.push(f"origin {branch}")


def handleCleanupPushMRE(mre):
    for e, repo, branch in zip(mre.exceptions(), mre.repos(), mre.branches()):
        try:
            raise e
        except grape_errors.GrapeGitError as e2:
            vine_logging.printMsg(f"Local and remote versions of {branch} may have diverged in {repo}")
            vine_logging.printMsg(f"{e2.gitOutput}")
            vine_logging.printMsg("Use grape pull to merge the remote version into the local version.")

def handleEnsureLocalUpToDateMRE(mre):
    _pushBranch = False
    _skipPush = False
    cleanupPushArgs = []
    for e1, repo, branch in zip(mre.exceptions(), mre.repos(), mre.branches()):
        try:
            raise e1
        except grape_errors.GrapeGitError as e:
            if ("[rejected]" in e.gitOutput and "(non-fast-forward)" in e.gitOutput) or "Couldn't find remote ref" in e.gitOutput:
                if "Couldn't find remote ref" in e.gitOutput:
                    if not _pushBranch:
                        vine_logging.printMsg(f"No remote reference to {branch} in {repo}'s origin. You may want to push this branch.")
                else:
                    vine_logging.printMsg(f"Fetch of {branch} rejected as non-fast-forward in repo {repo}")
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
                    vine_logging.printMsg(f"Skipping push of local {branch} in {repo}")

            elif e.commError:
                vine_logging.printMsg(f"Could not update {branch} from origin due to a connectivity issue. Checking out most recent\n"
                                      "local version. ")
            else:
                raise(e)

    # do another MRC launch to do any follow up pushes that were requested.
    multi_repo_cmd_launcher.MultiRepoCommandLauncher(cleanupPush, listOfRepoBranchArgTuples=cleanupPushArgs).launchFromWorkspaceDir(handleMRE=handleCleanupPushMRE)
    return

def safeSwitchWorkspaceToBranch(branch, checkoutArgs, sync):
    # Ensure local branches that you are about to check out are up to date with the remote
    if sync:
        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(ensureLocalUpToDateWithRemote, branch = branch, globalArgs=[checkoutArgs])
        launcher.launchFromWorkspaceDir(handleMRE=handleEnsureLocalUpToDateMRE)
    # Do a checkout
    # Pass False instead of sync since if sync is True ensureLocalUpToDateWithRemote will have already performed the fetch
    launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(checkout.handledCheckout, branch = branch, globalArgs=[checkoutArgs, False])
    launcher.launchFromWorkspaceDir(handleMRE=checkout.handleCheckoutMRE)


# Class for selecting subprojects in a workspace
class UVManager(object):
    def __init__(self, master, **kwargs):
        height = kwargs.get('height', 0)
        width  = kwargs.get('width', 0)

        # Saved lists of active subprojects (None if not saved)
        self.includedSubmodules = None
        self.includedNestedSubprojects = None
        self.saved = False

        self.master = master
        self.currentProjectIndex = None

        # 0 is submodules
        # 1 is nested subprojects
        self.activeSets = [ None, None ]
        self.inactiveSets = [ None, None ]
        self.originalActiveSets = [ None, None ]

        self.currentFrame = None
        self.currentActiveList = None
        self.currentInactiveList = None

        # Colors
        self.fginit     = kwargs.get('fginit', 'black')
        self.bginit     = kwargs.get('bginit', 'gray')
        self.fgselected = kwargs.get('fgselected', 'black')
        self.bgselected = kwargs.get('bgselected', 'goldenrod')
        self.fgchanged   = kwargs.get('fgchanged', 'blue')

        self.active = []
        self.inactive = []
        # offset so first call to createFrame starts at 0
        self.currentColumn = -2
        self.currentRow = 0

        # Main resizable window
        self.main = Tk.PanedWindow(master, height=height, width=width, sashwidth=4)
        controlpanel = Tk.Frame()
        savebutton = Tk.Button(controlpanel, text="Save and Update", command = self.saveChanges)
        savebutton.grid(row=0, column=0)
        cancelbutton = Tk.Button(controlpanel, text="Cancel", command = self.master.destroy)
        cancelbutton.grid(row=0, column=1)
        controlpanel.grid(row=0, column=0)

    # Save changes and exit
    def saveChanges(self):
        if self.activeSets[0] != None:
            self.saved = True
            self.includedSubmodules = {}
            for sub in self.activeSets[0]:
                self.includedSubmodules[sub] = True
            for sub in self.inactiveSets[0]:
                self.includedSubmodules[sub] = False
        if self.activeSets[1] != None:
            self.saved = True
            self.includedNestedSubprojects = {}
            for sub in self.activeSets[1]:
                self.includedNestedSubprojects[sub] = True
            for sub in self.inactiveSets[1]:
                self.includedNestedSubprojects[sub] = False
        self.master.destroy()

    # Save the original set of active subprojects and sort the last section
    def finalize(self):
        # sort the last section
        self.resortList(self.currentActiveList)
        self.resortList(self.currentInactiveList)

        # save the original state
        for i in [0, 1]:
            self.originalActiveSets[i] = set()
            for sub in self.activeSets[i]:
                self.originalActiveSets[i].add(sub)


    # Start a new frame for different project type
    def createFrame(self, projectType):
        self.currentRow = 2
        self.currentColumn = self.currentColumn + 2
        frame = Tk.Frame()
        label = Tk.Label(frame, text=f"Select {projectType}s")
        label.grid()
        frame.grid(row=1, column=self.currentColumn, columnspan=2)
        if projectType == "submodule":
            self.currentProjectIndex = 0
        elif projectType == "nested subproject":
            self.currentProjectIndex = 1

    # Start a new section for a different directory
    def createSection(self, directory):
        # sort the previous section (if any)
        if self.currentActiveList != None:
            self.resortList(self.currentActiveList)
            self.resortList(self.currentInactiveList)

        activepanel = Tk.Frame()
        activelabel = Tk.Label(activepanel, text=f"Active in {directory}")
        activescroll = Tk.Scrollbar(activepanel, width=10)
        activelist = Tk.Listbox(activepanel, background=self.bginit, foreground=self.fginit, selectbackground=self.bgselected, selectforeground=self.fgselected, yscrollcommand=activescroll.set, selectmode=Tk.SINGLE)
        activescroll.config(command=activelist.yview)
        activescroll.grid(row=2, column=0, sticky=Tk.N+Tk.S)
        activelabel.grid(row=0, column=0, columnspan=2)
        activelist.grid(row=2, column=1)
        activepanel.grid(row=self.currentRow, column=self.currentColumn)
        self.currentActiveList = activelist

        inactivepanel = Tk.Frame()
        inactivelabel = Tk.Label(inactivepanel, text=f"Inactive in {directory}")
        inactivescroll = Tk.Scrollbar(inactivepanel, width=10)
        inactivelist = Tk.Listbox(inactivepanel, background=self.bginit, foreground=self.fginit, selectbackground=self.bgselected, selectforeground=self.fgselected, yscrollcommand=inactivescroll.set, selectmode=Tk.SINGLE)
        inactivescroll.config(command=inactivelist.yview)
        inactivescroll.grid(row=2, column=0, sticky=Tk.N+Tk.S)
        inactivelabel.grid(row=0, column=0, columnspan=2)
        inactivelist.grid(row=2, column=1)
        inactivepanel.grid(row=self.currentRow, column=self.currentColumn+1)
        self.currentInactiveList = inactivelist

        self.currentRow = self.currentRow + 2

        index = self.currentProjectIndex
        activelist.bind("<Double-Button-1>", lambda e: self.deactivateProject(activelist, inactivelist,
                                                                              self.activeSets[index], self.inactiveSets[index], self.originalActiveSets[index]))
        inactivelist.bind("<Double-Button-1>", lambda e: self.activateProject(activelist, inactivelist,
                                                                              self.activeSets[index], self.inactiveSets[index], self.originalActiveSets[index]))

        activeall = Tk.Button(activepanel, text="activate all", borderwidth=0, foreground="darkblue",
                              command = lambda : self.activateAll(activelist, inactivelist,
                                                                   self.activeSets[index], self.inactiveSets[index], self.originalActiveSets[index]))
        activeall.grid(row=1, column=0, columnspan=2)
        inactiveall = Tk.Button(inactivepanel, text="deactivate all", borderwidth=0, foreground="darkblue",
                                command = lambda : self.deactivateAll(activelist, inactivelist,
                                                                       self.activeSets[index], self.inactiveSets[index], self.originalActiveSets[index]))
        inactiveall.grid(row=1, column=0, columnspan=2)


    # Create an entry for a subproject
    def createEntry(self, subproject, isActive):
        if self.activeSets[self.currentProjectIndex] == None:
            self.activeSets[self.currentProjectIndex] = set()
        if self.inactiveSets[self.currentProjectIndex] == None:
            self.inactiveSets[self.currentProjectIndex] = set()

        if isActive:
            self.currentActiveList.insert(Tk.END, subproject)
            self.activeSets[self.currentProjectIndex].add(subproject)
        else:
            self.currentInactiveList.insert(Tk.END, subproject)
            self.inactiveSets[self.currentProjectIndex].add(subproject)

    # Activate selected project
    def activateProject(self, activelist, inactivelist, activeset, inactiveset, originalactiveset):
        index = inactivelist.index(Tk.ACTIVE)
        entry = inactivelist.get(index)
        inactivelist.delete(index)
        inactiveset.remove(entry)
        activelist.insert(Tk.END, entry)
        activeset.add(entry)
        self.resortList(activelist, originalactiveset, self.fginit, self.fgchanged)
        self.resortList(inactivelist, originalactiveset, self.fgchanged, self.fginit)
        self.master.update()

    # Deactivate selected project
    def deactivateProject(self, activelist, inactivelist, activeset, inactiveset, originalactiveset):
        index = activelist.index(Tk.ACTIVE)
        entry = activelist.get(index)
        activelist.delete(index)
        activeset.remove(entry)
        inactivelist.insert(Tk.END, entry)
        inactiveset.add(entry)
        self.resortList(activelist, originalactiveset, self.fginit, self.fgchanged)
        self.resortList(inactivelist, originalactiveset, self.fgchanged, self.fginit)
        self.master.update()

    # Activate all projects in the section
    def activateAll(self, activelist, inactivelist, activeset, inactiveset, originalactiveset):
        entries = inactivelist.get(0, Tk.END)
        inactivelist.delete(0,Tk.END)
        for entry in entries:
            activelist.insert(Tk.END, entry)
            activeset.add(entry)
            inactiveset.remove(entry)
        self.resortList(activelist, originalactiveset, self.fginit, self.fgchanged)
        self.resortList(inactivelist, originalactiveset, self.fgchanged, self.fginit)
        self.master.update()

    # Deactivate all projects in the section
    def deactivateAll(self, activelist, inactivelist, activeset, inactiveset, originalactiveset):
        entries = activelist.get(0, Tk.END)
        activelist.delete(0,Tk.END)
        for entry in entries:
            inactivelist.insert(Tk.END, entry)
            inactiveset.add(entry)
            activeset.remove(entry)
        self.resortList(activelist, originalactiveset, self.fginit, self.fgchanged)
        self.resortList(inactivelist, originalactiveset, self.fgchanged, self.fginit)
        self.master.update()

    # Resort and format the list boxes
    def resortList(self, listbox, originalset = None, inSetColor = None, notInSetColor = None):
        entries = listbox.get(0, Tk.END)
        listbox.delete(0, Tk.END)
        for entry in sorted(entries):
            listbox.insert(Tk.END, entry)
            if originalset != None:
                if entry in originalset:
                    listbox.itemconfig(Tk.END, fg=inSetColor)
                else:
                    listbox.itemconfig(Tk.END, fg=notInSetColor)
