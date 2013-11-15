# Configure current repo
class Config(Option):
    """Configures the repo to be optimized for LC and GRAPE"""
    key = "config"
    section = section
    def Description(self):
        return "Initialize a repo you've already cloned without using GRAPE"
    def Execute(self):
        base = utility.gitDir()
        if base == "":
            return False
        dotGit = os.path.join(base,".git")

        print("optimizing git performance...")
        #runs file system intensive tasks such as git status and git commit
        # in parallel (important for NFS systems such as LC)
        git.config("core.preloadindex","true")

        #have git automatically do some garbage collection / optimizatoin
        git.config("gc.auto","1")

        #prevents false conflict detection due to differences in filesystem
        # time stamps
        git.config("core.trustctime","false")

        # stores login info for 12 hrs (max allowed by RZStash)
        git.config("credential.helper","cache --timeout=43200")

        # enables 'as' option for merge strategies -forces a conflict if two branches
        # modify the same file
        git.config("merge.verify.name","merge and verify driver")
        git.config("merge.verify.driver","./scripts/git/merge-and-verify-driver %A %O %B")

        # enables lg as an alias to print a pretty-font summary of
        # key junctions in the history for this branch.
        print("setting lg as an alias for a pretty log call...")
        git.config("alias.lg","log --graph --pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' --abbrev-commit --date=relative --simplify-by-decoration")
                 #enable sparse checkouts, something GRAPE needs for custom views
        git.config("core.sparseCheckout","true")

        # perform a sparse checkout if asked of us
        updateView = utility.userInput("do you want anything but the default view? (you can change this later using grape uv) [y/n","n")
        if updateView:
            sparseFile = os.path.join(dotGit,"info","sparse-checkout")
            with open(sparseFile,'w') as f:
                DefineView(f)
            checkout = utility.userInput("check out updated view? [y/n]","y")

            if checkout:
                git("read-tree","-mu","HEAD")

        # configure git to use p4merge for conflict resolution
        # and diffing
        useP4Merge = utility.userInput("Would you like to use p4merge as your merge tool? [y/n]","y")
        # note that this relies on p4merge being in your path somewhere
        if (useP4Merge):
            git.config("merge.keepBackup","false")
            git.config("merge.tool","p4merge")
            git.config("mergetool.keepBackup","false")
            git.config("mergetool.p4merge.cmd", "p4merge \"$BASE\" \"$LOCAL\" \"$REMOTE\" \"$MERGED\"")
            git.config("mergetool.p4merge.keepTemporaries","false")
            git.config("mergetool.p4merge.trustExitCode","false")
            git.config("mergetool.p4merge.keepBackup","false")
            print("configured repo to use p4merge for conflict resolution")

        useP4Diff = utility.userInput("Would you like to use p4merge as your diff tool? [y/n]","y")
        # this relies on p4diff being defined as a custom bash script, with the following one-liner:
        # [ $# -eq 7 ] && p4merge "$2" "$5"
        if (useP4Diff):
            git.config("diff.external","./scripts/git/p4diff")
            print("configured repo to use p4merge for diff calls")

        useGitP4 = utility.userInput("Would you like to use git-p4 to manage a perforce-git interface? [y/n]","n")
        if (useGitP4 ):
            git.config("git-p4.useclientspec","true")
            # create p4 references to enable imports from p4
            p4remotes = os.path.join(dotGit,"refs","remotes","p4","")
            utility.ensure_dir(p4remotes)
            commit = utility.userInput("Please enter a descriptor of the current git commit that mirrors the p4 repo","master")
            sha = utility.GetSHA(commit)
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
        return True
