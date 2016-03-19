import os
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
            git.fetch()
        utility.printMsg("Checking out %s in %s" % (branch, repo))
        git.checkout(checkoutargs + ' ' + branch)
    return True
    
def handleCheckoutMRE(mre):
    _skipBranchCreation = False
    _createNewBranch = False
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
                        utility.printMsg("Creating new branch %s in %s." % (branch, project))
                        git.checkout(checkoutargs[0]+" -b "+branch)
                        git.push("-u origin %s" % branch)
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
            
        
    
class Checkout(option.Option):
    """
    grape checkout
    
    Usage: grape-checkout  [-b] [--sync=<bool>] [--emailSubject=<sbj>] <branch> 

    Options:
    -b             Create the branch off of the current HEAD in each project.
    --sync=<bool>  Take extra steps to ensure the branch you check out is up to date with origin,
                   either by pushing or pulling the remote tracking branch.
                   [default: .grapeconfig.post-checkout.syncWithOrigin]


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

    @staticmethod
    def parseGitModulesDiffOutput(output, addedModules, removedModules):

        for line in output.split('\n'):
            if "+[submodule" in line:
                addedModules.append(line.split('"')[1])
            if "-[submodule" in line:
                removedModules.append(line.split('"')[1])

        return addedModules, removedModules
    
    @staticmethod
    def parseGrapeConfigNestedProjectDiffOutput(output, addedModules, removedModules): 
        nestedSection = False
        oldProjects = []
        newProjects = []
        for line in output.split('\n'): 
            ll = line.lower()
            if "[nestedprojects]" in ll:
                nestedSection = True
            elif "[" in ll and "]" in ll:
                nestedSection = False
            if nestedSection:
                if "-names" in ll: 
                    oldProjects = ll.split('=')[1].strip().split()
                if "+names" in ll:
                    newProjects = ll.split('=')[1].strip().split()
        for np in newProjects: 
            if np not in oldProjects:
                addedModules.append(np)
        for op in oldProjects:
            if op not in newProjects:
                removedModules.append(op)
                
        return addedModules, removedModules
            

    def execute(self, args):
        sync = args["--sync"].lower().strip()
        sync = sync == "true" or sync == "yes"
        args["--sync"] = sync
        checkoutargs = ''
        branch = args["<branch>"]
        if args['-b']: 
            checkoutargs += " -b"

        workspaceDir = utility.workspaceDir()
        os.chdir(workspaceDir)
        currentSHA = git.shortSHA("HEAD")

        utility.printMsg("Performing checkout of %s in outer level project." % branch)
        launcher = utility.MultiRepoCommandLauncher(handledCheckout, listOfRepoBranchArgTuples=[(workspaceDir, branch, [checkoutargs, sync])])
       
        if not launcher.launchFromWorkspaceDir(handleMRE=handleCheckoutMRE)[0]:
            return False
        previousSHA = currentSHA

        submoduleListDidChange = ".gitmodules" in git.diff("--name-only %s %s" % (previousSHA, branch))
        addedModules = []
        removedModules = []
        uvArgs = []
        submodulesDidChange = False
        if submoduleListDidChange and grapeConfig.grapeConfig().getboolean("workspace", "manageSubmodules"):

            self.parseGitModulesDiffOutput(git.diff("%s %s --no-ext-diff -- .gitmodules" % (previousSHA, branch)), addedModules,
                                           removedModules)
            if not addedModules and not removedModules:
                pass
            else:
                submodulesDidChange = True

                if removedModules:
                    for sub in removedModules:
                        try:
                            os.chdir(os.path.join(workspaceDir, sub))
                            if git.isWorkingDirectoryClean():
                                clean = utility.userInput("Would you like to remove the submodule %s ?" % sub, 'n')
                                if clean:
                                    utility.printMsg("Removing clean submodule %s." % sub)
                                    os.chdir(workspaceDir)
                                    shutil.rmtree(os.path.join(workspaceDir, sub))
                            else:
                                utility.printMsg("Unstaged / committed changes in %s, not removing." % sub)
                                os.chdir(workspaceDir)
                        except OSError:
                            pass


        # check to see if nested project list changed
        addedProjects = []
        removedProjects = []
        nestedProjectListDidChange = False
        os.chdir(workspaceDir)
        if ".grapeconfig" in git.diff("--name-only %s %s" % (previousSHA, branch)): 
            configDiff = git.diff("--no-ext-diff %s %s -- %s" % (previousSHA, branch, ".grapeconfig"))
            nestedProjectListDidChange = "[nestedprojects]" in configDiff.lower()
            self.parseGrapeConfigNestedProjectDiffOutput(configDiff, addedProjects, removedProjects)
            
            if removedProjects: 
                config = grapeConfig.grapeConfig()
                for proj in removedProjects:
                    projPrefix = config.get("nested-%s" % proj, "prefix")
                    try:
                        os.chdir(os.path.join(workspaceDir, proj))
                    except OSError as e:
                        if e.errno == 2:
                            # directory doesn't exist, that's OK since we're thinking about removing it
                            # anyways at this point...
                            continue
                    if git.isWorkingDirectoryClean():
                        remove = utility.userInput("Would you like to remove the nested subproject %s? \n"
                                                   "All work that has not been pushed will be lost. " % projPrefix, 'n'  )
                        if remove:
                            remove = utility.userInput("Are you sure? When you switch back to the previous branch, you will have to\n"
                                                       "reclone %s." % projPrefix, '\n')
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
            updateView = utility.userInput("Submodules or subprojects were added/removed as a result of this checkout. \n" + 
                                           "%s" % ("Added Projects: %s\n" % ','.join(addedProjects) if addedProjects else "") + 
                                           "%s" % ("Added Submodules: %s\n"% ','.join(addedModules) if addedModules else "") +
                                           "%s" % ("Removed Projects: %s\n" % ','.join(removedProjects) if removedProjects else "") +
                                           "%s" % ("Removed Submodules: %s\n" % ','.join(removedModules) if removedModules else "") +
                                           "Would you like to update your workspace view? [y/n]", 'n')
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
        grapeMenu.menu().applyMenuChoice('uv', uvArgs)

        os.chdir(workspaceDir)
        
        utility.printMsg("Switched to %s. Updating from remote..." % branch)
        if sync:
            if args["-b"]:
                grapeMenu.menu().applyMenuChoice("push")
            else:
                grapeMenu.menu().applyMenuChoice("pull")
        return True
    
    def setDefaultConfig(self, config):
        config.ensureSection("post-checkout")
        config.set("post-checkout", "syncWithOrigin", "True")
        pass


