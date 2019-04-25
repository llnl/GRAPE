import os
from grape.vine import config_parser_global
from grape.vine import config_parser_user
from grape.vine import grapeGit as git
from grape.vine import utility
from grape.vine import vine_logging
from grape.vine.option import Option


# Configure current repo
class Config(Option):
    """
    Configures the current repo to be optimized for GRAPE on LC
    Usage: grape-config [--uv [--uvArg=<arg>]... | --nouv] 
                        [--nocredcache | --credcache] [--p4merge] 
                        [--nop4merge] [--p4diff] [--nop4diff] [--git-p4]

    Options:
        --uv            walks you through setting up a sparse checkout for this repo. (interactive)
        --nouv          skips custom-view questions
        --credcache     enables https 12 hr credential cacheing. 
        --nocredcache   disables https 12 hr credential cacheing (this option recommended for Windows users)
        --p4merge       will set up p4merge as your merge tool. 
        --nop4merge     will skip p4merge questions.
        --p4diff        will set up p4merge as your diff tool. 
        --nop4diff      will skip p4diff questions.
        --git-p4        will configure your repo for use with git-p4 (deprecated)

    """

    def __init__(self):
        super(Config,self).__init__()
        self._key = "config"
        self._section = "Getting Started"

    def description(self):
        return "Initialize a repo you've already cloned without using GRAPE"

    def execute(self,args):
        from grape.vine import grapeMenu

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
        mergeVerifyPath = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                       "merge-and-verify-driver")
        
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

        # configure git to use p4merge for conflict resolution
        # and diffing

        useP4Merge = not args["--nop4merge"] and (args["--p4merge"] or utility.userInput("Would you like to use p4merge as your merge tool? [y/n]","y"))
        # note that this relies on p4merge being in your path somewhere
        if (useP4Merge):
            git.config("merge.keepBackup","false")
            git.config("merge.tool","p4merge")
            git.config("mergetool.keepBackup","false")
            git.config("mergetool.p4merge.cmd",'p4merge \"\$BASE\" \"\$LOCAL\" \"\$REMOTE\" \"\$MERGED\"')
            git.config("mergetool.p4merge.keepTemporaries","false")
            git.config("mergetool.p4merge.trustExitCode","false")
            git.config("mergetool.p4merge.keepBackup","false")
            vine_logging.printMsg("Configured repo to use p4merge for conflict resolution")
        else:
            git.config("merge.tool","tkdiff")

        useP4Diff = not args["--nop4diff"] and (args["--p4diff"] or utility.userInput("Would you like to use p4merge as your diff tool? [y/n]","y"))
        # this relies on p4diff being defined as a custom bash script, with the following one-liner:
        # [ $# -eq 7 ] && p4merge "$2" "$5"
        if useP4Diff:
            p4diffScript = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                        "p4diff")
            if os.path.exists(p4diffScript): 
                git.config("diff.external", p4diffScript)
                vine_logging.printMsg("Configured repo to use p4merge for diff calls - p4merge must be in your path")
            else: 
                vine_logging.printMsg(f"Could not find p4diff script at {p4diffScript}")
        useGitP4 = args["--git-p4"]
        if useGitP4:
            git.config("git-p4.useclientspec", "true")
            # create p4 references to enable imports from p4
            p4remotes = os.path.join(dotGit,"refs","remotes","p4","")
            utility.ensure_dir(p4remotes)
            commit = utility.userInput("Please enter a descriptor (e.g. SHA, branch if tip, tag name) of the current git commit that mirrors the p4 repo","master")
            sha = git.SHA(commit)
            with open(os.path.join(p4remotes,"HEAD"),'w') as f:
                f.write(sha)
            with open(os.path.join(p4remotes,"master"),'w') as f:
                f.write(sha)

            # to enable exports to p4, a maindev client needs to be set up
            haveCopied = False
            while (not haveCopied):
                p4settings = utility.userInput("Enter a path to a .p4settings file describing the maindev client you'd like to use for p4 updates",".p4settings")
                try:
                    shutil.copyfile(p4settings,os.path.join(base,".p4settings"))
                    haveCopied = True
                except:
                    print("could not find p4settings file, please check your path and try again")
                    return False

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
            if f"remotes/origin/{branch}" not in allBranches:
               missingBranches.append(branch)
            if (f"remotes/origin/{branch}" in allBranches) and (branch not in allBranches):
                vine_logging.printMsg(
                    f"Public branch {branch} does not have local version " +
                    f"in {repo}. Creating it now.")
                git.branch(f"{branch} origin/{branch}")
        if len(missingBranches) > 0:
            vine_logging.printMsg(
                "WARNING: the following public branches do not appear " +
                f"to exist on the remote origin of {repo}:\n" +
                f"{' '.join(missingBranches)}")
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
