import os
import re
import shutil

import grapeConfig
import grapeMenu
import option
import grapeGit as git
import utility


def handledCheckout(repo = '', branch = 'master', args = []):
    checkoutargs = args[0]
    sync = args[1]
    with utility.cd(repo):
        if sync:
           # attempt to fetch the requested branch
           try:
               git.fetch("origin", "%s:%s" % (branch, branch))
           except:
               # the branch may not exist, but ignore the exception
               # and allow the checkout to throw the exception.
               pass
        git.checkout(checkoutargs + ' ' + branch)
        utility.printMsg("Checked out %s in %s" % (branch, repo))
        
    return True

_skipBranchCreation = False
_createNewBranch = False
def handleCheckoutMRE(mre):
    global _skipBranchCreation
    global _createNewBranch
    newBranchReposArgTuples = []
    newBranches = []
    
    for e1, branch, project, checkoutargs in zip(mre.exceptions(), mre.branches(), mre.repos(), mre.args()):
        try:
            raise e1
        except git.GrapeGitError as e:
            with utility.cd(project):
                if "pathspec" in e.gitOutput:
                    createNewBranch = _createNewBranch
                    if _skipBranchCreation:
                        utility.printMsg("Skipping checkout of %s in %s" % (branch, project))
                        createNewBranch = False
                        
                    elif not createNewBranch:
                        createNewBranch =  utility.userInput("Branch not found locally or remotely. Would you like to create a "
                                                            "new branch called %s in %s? \n"
                                                        "(select 'a' to say yes for (a)ll, 's' to (s)kip creation for branches that don't exist )"
                                                            "\n(y,n,a,s)" % (branch, project), 'y')
                            
                    if str(createNewBranch).lower()[0] == 'a':
                        _createNewBranch = True
                        createNewBranch = True
                    if str(createNewBranch).lower()[0] == 's':
                        _skipBranchCreation = True
                        createNewBranch = False
                    if createNewBranch:
                        newBranchReposArgTuples.append((project, branch, {"checkout": checkoutargs[0]}))                        
                    else:
                            continue
    
                elif "already exists" in e.gitOutput:
                    utility.printMsg("Branch %s already exists in %s." % (branch, project))
                    branchDescription = git.commitDescription(branch)
                    headDescription = git.commitDescription("HEAD")
                    if branchDescription == headDescription:
                        utility.printMsg("Branch %s and HEAD are the same. Switching to %s." % (branch, branch))
                        action = "k"
                    else:
                        utility.printMsg("Branch %s and HEAD are not the same." % branch)
                        action = ''
                        valid = False
                        while not valid:
                            action = utility.userInput("Would you like to \n (k)eep it as is at: %s \n"
                                                       " or \n (f)orce it to: %s? \n(k,f)" %
                                                       (branchDescription, headDescription), 'k')
                            valid = (action == 'k') or (action == 'f')
                            if not valid:
                                utility.printMsg("Invalid input. Enter k or f. ")
                    if action == 'k':
                        git.checkout(branch)
                    elif action == 'f':
                        git.checkout("-B %s" % branch)
                elif "conflict" in e.gitOutput.lower(): 
                    utility.printMsg("CONFLICT occurred when pulling %s from origin." % branch)
                elif "does not appear to be a git repository" in e.gitOutput.lower():
                    utility.printMsg("Remote 'origin' does not exist. "
                                     "This branch was not updated from a remote repository.")
                elif "Couldn't find remote ref" in e.gitOutput:
                    utility.printMsg("Remote of %s does not have reference to %s. You may want to push this branch. " %(project, branch))
                else:
                    raise e
            
    if len(newBranchReposArgTuples) > 0:
        utility.MultiRepoCommandLauncher(createNewBranches, listOfRepoBranchArgTuples=newBranchReposArgTuples).launchFromWorkspaceDir(handleMRE=createNewBranchesMREHandler)

def createNewBranches(repo='', branch='', args={}):
    project = repo
    checkoutargs = args["checkout"]
    with utility.cd(project):
        utility.printMsg("Creating new branch %s in %s." % (branch, project))
        git.checkout(checkoutargs+" -b "+branch)
        git.push("-u origin %s" % branch)
    return True

def createNewBranchesMREHandler(mre):
    for e, b in zip(mre.exceptions(), mre.branches()):
        print b, e
     
def parseGitModulesDiffOutput(currentSHA, branch, addedModules, removedModules, changedURLModules):
    cwd = os.getcwd() 
    os.chdir(utility.workspaceDir())
    submoduleListWillChange = ".gitmodules" in git.diff("--name-only %s %s" % (currentSHA, branch))
    if submoduleListWillChange:
       output = git.diff("%s %s --no-ext-diff -- .gitmodules" % (currentSHA, branch))
       currentSubmodule = False
       for line in output.split('\n'):
           if "[submodule" in line:
               currentSubmodule = line.split('"')[1]
           # This relies on the diff context being sufficient to catch the submodule line.
           # Only 2 lines of backwards context should be required, so this should be ok.
           if re.match("-\s+url\s*=", line):
               if currentSubmodule:
                  changedURLModules.append(currentSubmodule)
           if "+[submodule" in line:
               addedModules.append(line.split('"')[1])
               currentSubmodule = False
           if "-[submodule" in line:
               removedModules.append(line.split('"')[1])
               currentSubmodule = False
    os.chdir(cwd)

    return addedModules, removedModules, changedURLModules

def cleanSubmodule(sub, args, changedURL = False, activeSubmodules = []):
    cwd = os.getcwd() 
    workspaceDir = utility.workspaceDir()
    cleaned = False
    try:
        os.chdir(os.path.join(workspaceDir, sub))
        workingDirClean = git.isWorkingDirectoryClean()
        changedActive = sub in activeSubmodules
        if workingDirClean or (changedURL and not changedActive):
            # we must clean out any submodules that changed URLs
            if changedURL:
               unpushed = False
               if changedActive:
                  unpushed = git.log("--branches --not --remotes --oneline --decorate")
               if unpushed:
                  utility.printMsg("You have unpushed changed in %s:\n%s" % (sub, unpushed))
                  clean = utility.userInput("Would you like to remove the submodule %s (this will discard your unpushed changes)?" % sub, 'n')
               else:
                   clean = True
            else:
               cleanBehaviorSet = args["--noUpdateView"] or args["--updateView"]
               if not cleanBehaviorSet:
                   clean = utility.userInput("Would you like to remove the submodule %s ?" % sub, 'n')
               elif args["--noUpdateView"]:
                   clean = False
               elif args["--updateView"]:
                   clean = True
            if clean:
                utility.printMsg("Removing clean submodule %s." % sub)
                if not changedURL or changedActive:
                   shutil.rmtree(os.path.join(workspaceDir, sub))
                if changedURL:
                   if changedActive:
                      os.chdir(workspaceDir)
                      git.submodule("deinit -f %s" % sub)
                   # This must be removed even for inactive submodules
                   if os.path.exists(os.path.join(workspaceDir, ".git", "modules", sub)):
                      shutil.rmtree(os.path.join(workspaceDir, ".git", "modules", sub))
                cleaned = True
        else:
            utility.printMsg("Unstaged / committed changes in %s, not removing." % sub)

    except OSError:
        pass
    os.chdir(cwd)
    return cleaned

        
class Checkout(option.Option):
    """
    grape checkout
    
    Usage: grape-checkout  [-b] [--sync=<bool>] [--emailSubject=<sbj>] [--updateView] [--noUpdateView] <branch>

    Options:
    -b                  Create the branch off of the current HEAD in each project.
    --sync=<bool>       Take extra steps to ensure the branch you check out is up to date with origin,
                        either by pushing or pulling the remote tracking branch.
                        [default: .grapeconfig.post-checkout.syncWithOrigin]
    --updateView        If your submodules / nested projects change, change your workspace to match the changes.
                        Warning - setting this may cause you to lose unpushed work in nested subprojects.
    --noUpdateView      If your submodules / nested projects change, do not change your workspace to match the changes.


    Arguments:
    <branch>    The name of the branch to checkout. 

    """
    def __init__(self):
        super(Checkout, self).__init__()
        self._key = "checkout"
        self._section = "Workspace"
        self._createNewBranch = False
        self._skipBranchCreation = False

    def description(self):
        return "Checks out a branch in all projects in this workspace."

    def execute(self, args):
        sync = args["--sync"].lower().strip()
        sync = sync == "true" or sync == "yes"
        args["--sync"] = sync
        branch = args["<branch>"]

        workspaceDir = utility.workspaceDir()
        os.chdir(workspaceDir)
        currentSHA = git.shortSHA("HEAD")

        # check to see if we already have the branch
        try:
            git.shortSHA(branch)
        except:
            # otherwise fetch it
            git.fetch("origin", "%s:%s" % (branch, branch))

        addedModules = []
        removedModules = []
        changedURLModules = []
        uvArgs = []
        if grapeConfig.grapeConfig().getboolean("workspace", "manageSubmodules"):
            parseGitModulesDiffOutput(currentSHA, branch, addedModules, removedModules, changedURLModules)

        submodulesDidChange = False
        if addedModules or removedModules or changedURLModules:
            submodulesDidChange = True
             
        # deinit and clean out any submodules that changed urls
        initiallyActiveSubmodules = git.getActiveSubmodules()
        for sub in changedURLModules:
            utility.printMsg("url for %s changed, attempting to remove references for %s submodule." % (sub, "active" if sub in initiallyActiveSubmodules else "inactive") )
            cleaned = cleanSubmodule(sub, args, True, initiallyActiveSubmodules)
            if not cleaned:
                utility.printMsg("Failed to remove old submodule for %s." % sub)
                return False

        checkoutargs = ''
        if args['-b']: 
            checkoutargs += " -b"
        utility.printMsg("Performing checkout of %s in outer level project." % branch)
        launcher = utility.MultiRepoCommandLauncher(handledCheckout, listOfRepoBranchArgTuples=[(workspaceDir, branch, [checkoutargs, sync])])
       
        if not launcher.launchFromWorkspaceDir(handleMRE=handleCheckoutMRE)[0]:
            return False

        previousSHA = currentSHA

        # reinit any submodules with changed urls
        for sub in changedURLModules:
            if sub in initiallyActiveSubmodules:
                git.submodule("init %s" % sub)

        # clean out and removed submodules
        for sub in removedModules:
            cleaned = cleanSubmodule(sub, args)

        # check to see if nested project list changed
        nestedProjectListDidChange = False
        os.chdir(workspaceDir)
        addedProjects = []
        removedProjects = []
        if ".grapeconfig" in git.diff("--name-only %s %s" % (previousSHA, branch)):
            previousConfig = grapeConfig.GrapeConfigParser(configString=git.show("%s:.grapeconfig" % previousSHA))
            branchConfig = grapeConfig.GrapeConfigParser(configString=git.show("%s:.grapeconfig" % branch))
            previousNestedProjects = set(previousConfig.getAllNestedSubprojects())
            branchNestedProjects = set(branchConfig.getAllNestedSubprojects())
            # use set subtraction to figure out the removed and added projects
            removedProjects = previousNestedProjects - branchNestedProjects
            addedProjects = branchNestedProjects - previousNestedProjects
            nestedProjectListDidChange = bool(removedProjects or addedProjects)

            if removedProjects: 
                config = grapeConfig.grapeConfig()
                for proj in removedProjects:
                    projPrefix = previousConfig.get("nested-%s" % proj, "prefix")
                    try:
                        os.chdir(os.path.join(workspaceDir, proj))
                    except OSError as e:
                        if e.errno == 2:
                            # directory doesn't exist, that's OK since we're thinking about removing it
                            # anyways at this point...
                            continue
                    if git.isWorkingDirectoryClean():
                        removeBehaviorSet = args["--noUpdateView"] or args["--updateView"]
                        if not removeBehaviorSet:
                            remove = utility.userInput("Would you like to remove the nested subproject %s? \n"
                                                       "All work that has not been pushed will be lost. " % projPrefix, 'n'  )
                        elif args["--noUpdateView"]:
                            remove = False
                        elif args["--updateView"]:
                            remove = True
                        if remove:
                            remove = utility.userInput("Are you sure you want to remove %s? When you switch back to the previous branch, you will have to\n"
                                                       "reclone %s." % (projPrefix, projPrefix), 'n')
                        if remove:
                            os.chdir(workspaceDir)
                            shutil.rmtree(os.path.join(workspaceDir,projPrefix))
                    else:
                        utility.printMsg("Unstaged / committed changes in %s, not removing. \n"
                                         "Note this project is NOT active in %s. " % (projPrefix, branch))
                        os.chdir(workspaceDir)                          
                        
        if not submodulesDidChange and not nestedProjectListDidChange:
            uvArgs.append("--checkSubprojects")
        else:
            updateViewSet = args["--noUpdateView"] or args["--updateView"]
            if not updateViewSet:
                updateView = utility.userInput("Submodules or subprojects were added/removed as a result of this checkout. \n" + 
                                               "%s" % ("Added Projects: %s\n" % ','.join(addedProjects) if addedProjects else "") + 
                                               "%s" % ("Added Submodules: %s\n"% ','.join(addedModules) if addedModules else "") +
                                               "%s" % ("Removed Projects: %s\n" % ','.join(removedProjects) if removedProjects else "") +
                                               "%s" % ("Removed Submodules: %s\n" % ','.join(removedModules) if removedModules else "") +
                                               "Would you like to update your workspace view? [y/n]", 'n')
            elif args["--noUpdateView"]:
                updateView = False
            elif args["--updateView"]:
                updateView = True
            if not updateView:
                uvArgs.append("--checkSubprojects")
            
        if args["-b"]: 
            uvArgs.append("-b")
        if sync:
            uvArgs.append("--sync=True")
        else:
            uvArgs.append("--sync=False")

        # in case the user switches to a branch without corresponding branches in the submodules, make sure active submodules
        # are at the right commit before possibly creating new branches at the current HEAD. 
        git.submodule("update")
        utility.printMsg("Calling grape uv %s to ensure branches are consistent across all active subprojects and submodules." % ' '.join(uvArgs))
        grapeConfig.read()
        grapeMenu.menu().applyMenuChoice('uv', uvArgs)

        os.chdir(workspaceDir)
        
        if sync:
            utility.printMsg("Switched to %s. Updating from remote...\n\t (use --sync=False or .grapeconfig.post-checkout.syncWithOrigin to change behavior.)" % branch)            
            if args["-b"]:
                grapeMenu.menu().applyMenuChoice("push")
            else:
                grapeMenu.menu().applyMenuChoice("pull")
        else:
            utility.printMsg("Switched to %s." % branch)
            
        global _skipBranchCreation
        global _createNewBranch
        _skipBranchCreation = False
        _createNewBranch = False        
        return True
    
    def setDefaultConfig(self, config):
        config.ensureSection("post-checkout")
        config.set("post-checkout", "syncWithOrigin", "True")
        pass


