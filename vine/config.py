import option, utility
import grapeGit as git
import os
import grapeMenu
# Configure current repo
class Config(option.Option):
    """
    Configures the current repo to be optimized for GRAPE on LC
    Usage: grape-config [--cv | --nocv] [--nocredcache] [--p4merge] 
                        [--nop4merge] [--p4diff] [--nop4diff] [--git-p4]

    Options:
        --cv            walks you through setting up a sparse checkout for this repo. (interactive)
        --nocv          skips custom-view questions
        --nocredcache   disables https 12 hr credential cacheing (this option recommended for Windows users)
        --p4merge       will set up p4merge as your merge tool. 
        --nop4merge     will skip p4merge questions.
        --p4diff        will set up p4merge as your diff tool. 
        --nop4diff      will skip p4diff questions.
        --git-p4        will configure your repo for use with git-p4 (deprecated)

    """

    def __init__(self):
        self._key = "config"
        self._section = "Getting Started"

    def description(self):
        return "Initialize a repo you've already cloned without using GRAPE"

    def execute(self,args):
        base = git.baseDir()
        if base == "":
            return False
        dotGit = git.gitDir()
         
        print("optimizing git performance on slow file systems...")
        #runs file system intensive tasks such as git status and git commit
        # in parallel (important for NFS systems such as LC)
        git.config("core.preloadindex","true")

        #have git automatically do some garbage collection / optimizatoin
        print("setting up automatic git garbage collection...")
        git.config("gc.auto","1")

        #prevents false conflict detection due to differences in filesystem
        # time stamps
        print("Optimizing cross platform portability...")
        git.config("core.trustctime","false")

        # stores login info for 12 hrs (max allowed by RZStash)
        if not args["--nocredcache"]: 
            print("Enabling 12 hr caching of https credentials...")
            git.config("--global credential.helper","cache --timeout=43200")

        # enables 'as' option for merge strategies -forces a conflict if two branches
        # modify the same file
        mergeVerifyPath = os.path.join(os.path.dirname(__file__),"..","merge-and-verify-driver")
        
        if os.path.exists(mergeVerifyPath): 
           print("Enabling safe merges (triggers conflicts any time same file is modified),\n\t see 'as' option for grape m and grape md...")
           git.config("merge.verify.name","merge and verify driver")
           git.config("merge.verify.driver","%s/merge-and-verify-driver %A %O %B")
        else:
           print("WARNING: merge and verify script not detected, safe merges ('as' option to grape m / md) will not work!")
        # enables lg as an alias to print a pretty-font summary of
        # key junctions in the history for this branch.
        print("setting lg as an alias for a pretty log call...")
        git.config("alias.lg","log --graph --pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' --abbrev-commit --date=relative --simplify-by-decoration")
        
        # perform an update of the active submodules if asked. 
        ask = not args["--nocv"]
        updateView = ask and (args["--cv"] or utility.userInput("do you want any submodules? (you can change this later using grape uv) [y/n]","n") )
        if updateView:
            grapeMenu.menu().applyMenuChoice("uv")

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
            print("configured repo to use p4merge for conflict resolution")
        else:
            git.config("merge.tool","tkdiff")

        useP4Diff = not args["--nop4diff"] and (args["--p4diff"] or utility.userInput("Would you like to use p4merge as your diff tool? [y/n]","y"))
        # this relies on p4diff being defined as a custom bash script, with the following one-liner:
        # [ $# -eq 7 ] && p4merge "$2" "$5"
        if (useP4Diff):
            p4diffScript = os.path.join(os.path.dirname(__file__),"..","p4diff")
            if os.path.exists(p4diffScript): 
               git.config("diff.external",p4diffScript)
               print("configured repo to use p4merge for diff calls - p4merge must be in your path")
            else: 
               print("Could not find p4diff script at %s" % p4diffScript)
        else:
            #revert diff.external to the default value
            git.config("diff.external","")
        useGitP4 = args["--git-p4"]
        if (useGitP4 ):
            git.config("git-p4.useclientspec","true")
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
        print("Installing hooks in all repos")
        cwd = git.baseDir()
        grapeMenu.menu().applyMenuChoice("installHooks",["installHooks"])
        os.chdir(cwd)
        for sub in git.getActiveSubmodules(False):
            os.chdir(os.path.join(cwd,sub))
            grapeMenu.menu().applyMenuChoice("installHooks",["installHooks"])
        os.chdir(cwd)
        return True

    def setDefaultConfig(self, config):
        pass
