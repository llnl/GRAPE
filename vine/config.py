
import os

import config_parser_global
import config_parser_user
import grapeGit as git
import option
import vine_logging
import utility

# Configure current repo
class Config(option.Option):
    """
    Configures the current repo to be optimized for GRAPE on LC
    Usage: grape-config [--uv [--uvArg=<arg>]... | --nouv] 
                        [--nocredcache | --credcache]

    Options:
        --uv            walks you through setting up a sparse checkout for this repo. (interactive)
        --nouv          skips custom-view questions
        --credcache     enables https 12 hr credential cacheing. 
        --nocredcache   disables https 12 hr credential cacheing (this option recommended for Windows users)

    """

    def __init__(self):
        super(Config,self).__init__()
        self._key = "config"
        self._section = "Getting Started"

    def description(self):
        return "Initialize a repo you've already cloned without using GRAPE"

    def execute(self,args):
        import grapeMenu

        base = git.baseDir()
        if base == "":
            return False
        dotGit = git.gitDir()
         
        vine_logging.printMsg("Optimizing git performance on slow file systems...")
        #runs file system intensive tasks such as git status and git commit
        # in parallel (important for NFS systems such as LC)
        git.config("core.preloadindex","true")

        #have git automatically do some garbage collection / optimization
        vine_logging.printMsg("Setting up automatic git garbage collection...")
        git.config("gc.auto","1")

        #prevents false conflict detection due to differences in filesystem
        # time stamps
        vine_logging.printMsg("Optimizing cross platform portability...")
        git.config("core.trustctime","false")

        # stores login info for 12 hrs (max allowed by RZBitbucket)

        if not args["--nocredcache"]:
            cache = args["--credcache"]
            if not cache:
                cache = utility.userInput("Would you like to enable git-managed credential caching?", 'y')
            if cache:
                vine_logging.printMsg("Enabling 12 hr caching of https credentials...")
                if os.name == "nt":
                    git.config("--global credential.helper", "wincred")
                else :
                    git.config("--global credential.helper", "cache --timeout=43200")

        # enables 'as' option for merge strategies -forces a conflict if two branches
        # modify the same file
        mergeVerifyPath = os.path.join(os.path.dirname(__file__),"..","merge-and-verify-driver")
        
        if os.path.exists(mergeVerifyPath): 
            vine_logging.printMsg("Enabling safe merges (triggers conflicts any time same file is modified),\n\t see 'as' option for grape m and grape md...")
            git.config("merge.verify.name","merge and verify driver")
            git.config("merge.verify.driver","%s/merge-and-verify-driver %A %O %B")
        else:
            vine_logging.printMsg("WARNING: merge and verify script not detected, safe merges ('as' option to grape m / md) will not work!")
        # enables lg as an alias to print a pretty-font summary of
        # key junctions in the history for this branch.
        vine_logging.printMsg("Setting lg as an alias for a pretty log call...")
        git.config("alias.lg","log --graph --pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' --abbrev-commit --date=relative --simplify-by-decoration")
        
        # perform an update of the active subprojects if asked.
        ask = not args["--nouv"]
        updateView = ask and (args["--uv"] or utility.userInput("Do you want to edit your active subprojects?"
                                                                " (you can do this later using grape uv) [y/n]", "n"))
        if updateView:
            grapeMenu.menu().applyMenuChoice("uv", args["--uvArg"])

        git.config("merge.tool","tkdiff")

        # install hooks here and in all submodules
        vine_logging.printMsg("Installing hooks in all repos...")
        cwd = git.baseDir()
        grapeMenu.menu().applyMenuChoice("installHooks")
        
        #  ensure all public branches are available in all repos
        submodules = git.getActiveSubmodules(utility.workspaceDir())
        config = config_parser_global.grapeConfig()
        publicBranches = config.getPublicBranchList()
        submodulePublicBranches = set(config.getMapping(self.SECTION_WORKSPACE, 'submoduleTopicPrefixMappings').values())
        for sub in submodules:
            self.ensurePublicBranchesExist(sub, submodulePublicBranches)
        
        # reset config to the workspace grapeconfig, use that one for all nested projects' public branches.
        wsDir = utility.workspaceDir()
        for proj in config_parser_user.getAllActiveNestedSubprojectPrefixes():
            self.ensurePublicBranchesExist(os.path.join(wsDir,proj), publicBranches)
        
        self.ensurePublicBranchesExist(wsDir, publicBranches)
            
        return True

    def setDefaultConfig(self, config):
        pass
    
    @staticmethod
    def ensurePublicBranchesExist(repo, publicBranches):
        cwd =  os.getcwd()
        os.chdir(repo)
        allBranches = git.allBranches()
        missingBranches = []
        for branch in publicBranches:
            if ("remotes/origin/%s" % branch) not in allBranches:
               missingBranches.append(branch)
            if ("remotes/origin/%s" % branch in allBranches) and (branch not in allBranches):
                vine_logging.printMsg("Public branch %s does not have local version in %s. Creating it now." % (branch, repo))
                git.branch("%s origin/%s" % (branch, branch))
        if len(missingBranches) > 0:
            vine_logging.printMsg("WARNING: the following public branches do not appear to exist on the remote origin of %s:\n%s" % (repo, " ".join(missingBranches)))
        os.chdir(cwd)
        
    @staticmethod
    def checkIfPublicBranchesExist(repo, publicBranches):
        origcwd =  os.getcwd()
        os.chdir(repo)
        allBranches = git.allBranches()
        missingBranches = []
        for branch in publicBranches:
            if (branch not in allBranches):
                missingBranches.append(branch)
        os.chdir(origcwd)
        return missingBranches
