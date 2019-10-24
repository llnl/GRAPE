import logging
import os
import shutil
from vine import config_parser_global
from vine import config_parser_user
from vine import grapeGit as git
from vine import utility
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.option import Option
from vine.vine_logging import log_wrapper


# Configure current repo
class Config(Option, WorkspaceDirHandler):
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
        super(Config, self).__init__()
        self._key = "config"
        self._section = "Getting Started"

    def description(self):
        return "Initialize a repo you've already cloned without using GRAPE"

    @log_wrapper
    def execute(self, args):
        from vine import grapeMenu

        base = git.baseDir(execution_path=self.workspace_dir)
        if base == "":
            return False
        dotGit = git.gitDir(execution_path=self.workspace_dir)

        logging.info("Optimizing git performance on slow file systems...")
        #runs file system intensive tasks such as git status and git commit
        # in parallel (important for NFS systems such as LC)
        git.config("core.preloadindex","true", execution_path=self.workspace_dir)

        #have git automatically do some garbage collection / optimization
        logging.info("Setting up automatic git garbage collection...")
        git.config("gc.auto", "1", execution_path=self.workspace_dir)

        #prevents false conflict detection due to differences in filesystem
        # time stamps
        logging.info("Optimizing cross platform portability...")
        git.config("core.trustctime", "false", execution_path=self.workspace_dir)

        # stores login info for 12 hrs (max allowed by RZBitbucket)

        if not args["--nocredcache"]:
            cache = args["--credcache"]
            if not cache:
                cache = utility.userInput("Would you like to enable git-managed credential caching?", 'y')
            if cache:
                logging.info("Enabling 12 hr caching of https credentials...")
                if os.name == "nt":
                    git.config("--global credential.helper", "wincred", execution_path=self.workspace_dir)
                else :
                    git.config("--global credential.helper", "cache --timeout=43200", execution_path=self.workspace_dir)

        # enables 'as' option for merge strategies -forces a conflict if two branches
        # modify the same file
        mergeVerifyPath = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                       "merge-and-verify-driver")

        if os.path.exists(mergeVerifyPath):
            logging.info("Enabling safe merges (triggers conflicts any time same file is modified),\n\t see 'as' option for grape m and grape md...")
            git.config("merge.verify.name","merge and verify driver", execution_path=self.workspace_dir)
            git.config("merge.verify.driver","%s/merge-and-verify-driver %A %O %B", execution_path=self.workspace_dir)
        else:
            logging.warning("WARNING: merge and verify script not detected, safe merges ('as' option to grape m / md) will not work!")
        # enables lg as an alias to print a pretty-font summary of
        # key junctions in the history for this branch.
        logging.info("Setting lg as an alias for a pretty log call...")
        git.config("alias.lg", "log --graph --pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' --abbrev-commit --date=relative --simplify-by-decoration", execution_path=self.workspace_dir)

        # perform an update of the active subprojects if asked.
        ask = not args["--nouv"]
        updateView = ask and (args["--uv"] or utility.userInput("Do you want to edit your active subprojects?"
                                                                " (you can do this later using grape uv) [y/n]", "n"))
        menu = grapeMenu.menu()
        menu.set_workspace_dir(self.workspace_dir)
        if updateView:
            menu.applyMenuChoice("uv", args["--uvArg"])

        # configure git to use p4merge for conflict resolution
        # and diffing

        useP4Merge = not args["--nop4merge"] and (args["--p4merge"] or utility.userInput("Would you like to use p4merge as your merge tool? [y/n]","y"))
        # note that this relies on p4merge being in your path somewhere
        if (useP4Merge):
            git.config("merge.keepBackup", "false", execution_path=self.workspace_dir)
            git.config("merge.tool", "p4merge", execution_path=self.workspace_dir)
            git.config("mergetool.keepBackup", "false", execution_path=self.workspace_dir)
            git.config("mergetool.p4merge.cmd", 'p4merge \"\$BASE\" \"\$LOCAL\" \"\$REMOTE\" \"\$MERGED\"', execution_path=self.workspace_dir)
            git.config("mergetool.p4merge.keepTemporaries", "false", execution_path=self.workspace_dir)
            git.config("mergetool.p4merge.trustExitCode", "false", execution_path=self.workspace_dir)
            git.config("mergetool.p4merge.keepBackup", "false", execution_path=self.workspace_dir)
            logging.info("Configured repo to use p4merge for conflict resolution")
        else:
            git.config("merge.tool", "tkdiff", execution_path=self.workspace_dir)

        useP4Diff = not args["--nop4diff"] and (args["--p4diff"] or utility.userInput("Would you like to use p4merge as your diff tool? [y/n]","y"))
        # this relies on p4diff being defined as a custom bash script, with the following one-liner:
        # [ $# -eq 7 ] && p4merge "$2" "$5"
        if useP4Diff:
            p4diffScript = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                        "p4diff")
            if os.path.exists(p4diffScript):
                git.config("diff.external", p4diffScript, execution_path=self.workspace_dir)
                logging.info("Configured repo to use p4merge for diff calls - p4merge must be in your path")
            else:
                logging.info(f"Could not find p4diff script at {p4diffScript}")
        useGitP4 = args["--git-p4"]
        if useGitP4:
            git.config("git-p4.useclientspec", "true", execution_path=self.workspace_dir)
            # create p4 references to enable imports from p4
            p4remotes = os.path.join(dotGit, "refs", "remotes", "p4", "")
            utility.ensure_dir(p4remotes)
            commit = utility.userInput("Please enter a descriptor (e.g. SHA, branch if tip, tag name) of the current git commit that mirrors the p4 repo","master")
            sha = git.SHA(commit, execution_path=self.workspace_dir)
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
                    logging.warning("Could not find p4settings file, please check your path and try again")
                    return False

        # install hooks here and in all submodules
        logging.info("Installing hooks in all repos...")
        menu.applyMenuChoice("installHooks")

        #  ensure all public branches are available in all repos
        submodules = git.getActiveSubmodules(execution_path=self.workspace_dir)
        config = config_parser_global.grapeConfig()
        publicBranches = config.getPublicBranchList()
        submodulePublicBranches = set(config.getMapping(self.SECTION_WORKSPACE, 'submoduleTopicPrefixMappings').values())
        for sub in submodules:
            config.read(sub)
            self.ensurePublicBranchesExist(sub, submodulePublicBranches)

        config.read(self.workspace_dir)

        # reset config to the workspace grapeconfig, use that one for all nested projects' public branches.
        for proj in config_parser_user.getAllActiveNestedSubprojectPrefixes(workspaceDir=self.workspace_dir):
            self.ensurePublicBranchesExist(os.path.join(self.workspace_dir, proj), publicBranches)

        self.ensurePublicBranchesExist(self.workspace_dir, publicBranches)

        return True

    def setDefaultConfig(self, config):
        pass

    @staticmethod
    def ensurePublicBranchesExist(repo, publicBranches):
        allBranches = git.allBranches(execution_path=repo)
        missingBranches = []
        for branch in publicBranches:
            if f"remotes/origin/{branch}" not in allBranches:
                missingBranches.append(branch)
            if (f"remotes/origin/{branch}" in allBranches) and (branch not in allBranches):
                logging.info(
                    f"Public branch {branch} does not have local version " +
                    f"in {repo}. Creating it now.")
                git.branch(f"{branch} origin/{branch}", execution_path=repo)
        if missingBranches:
            logging.warning(
                "WARNING: the following public branches do not appear " +
                f"to exist on the remote origin of {repo}:\n" +
                f"{' '.join(missingBranches)}")

    @staticmethod
    def checkIfPublicBranchesExist(repo, publicBranches):
        allBranches = git.allBranches(execution_path=repo)
        missingBranches = [branch for branch in publicBranches
                           if branch not in allBranches]
        return missingBranches
