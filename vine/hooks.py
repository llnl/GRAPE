import configparser
import io
import logging
import os
from vine import config_parser_base
from vine import config_parser_user
from vine import grape_errors
from vine import grapeGit as git
from vine import utility
from vine import vine_logging
from vine.command_path_handler import CommandPathHandler
from vine.option import Option
from vine.vine_logging import log_wrapper


def getActiveSubprojects(*, workspace_dir):
    active_submodules = git.getActiveSubmodules(execution_path=workspace_dir)
    active_nested_subproject_prefixes = \
        config_parser_user.getAllActiveNestedSubprojectPrefixes(workspaceDir=workspace_dir)
    return active_submodules + active_nested_subproject_prefixes


#option that installs wrapper calls to grape as git hooks in this repo.
class InstallHooks(Option, CommandPathHandler):
    """ grape installHooks
    Installs callbacks to grape in .git/hooks, allowing grape-configurable hooks to be used
    in this repo.

    Usage: grape-installHooks [--noRecurse] [--toInstall=<hook>]...

    Options:
    --noRecurse           If set, do not recurse into submodules and nested subprojects.
    --toInstall=<hook>    the list of hook-types to install
                          [default: pre-commit pre-push pre-rebase post-commit post-rebase post-merge post-checkout]

    """

    def __init__(self):
        super(InstallHooks, self).__init__()
        self._key = "installHooks"
        self._section = "Hooks"

    def description(self):
        return "Installs grape as your hook manager for this repo. \n" \
               "\t\t(May overwrite existing hooks you have installed in this repo)"

    def installHooksInRepo(self, repo, args):
        header = "#!/Git/sh\n" if os.name == 'nt' else "#!/bin/sh\n"
        hooks = args["--toInstall"]
        for h in hooks:
            hook_path = os.path.join(git.gitDir(
                execution_path=self.command_path), "hooks", h)
            with io.open(hook_path, 'w') as file_:
                file_.write(header)
                grapeCmd = utility.getGrapeExec()
                file_.write(f"{grapeCmd} runHook {h} \"$@\" \n\n")
            os.chmod(hook_path, 0o755)

    @log_wrapper
    def execute(self, args):
        logging.info(f"Installing hooks in {self.workspace_dir}.")
        self.installHooksInRepo(self.workspace_dir, args)
        if not args["--noRecurse"]:
            for sub in getActiveSubprojects(workspace_dir=self.workspace_dir):
                logging.info(f"Installing hooks in {sub}.")
                self.installHooksInRepo(os.path.join(self.workspace_dir, sub), args)
        return True

    def setDefaultConfig(self, config):
        pass


class RunHook(Option, CommandPathHandler):
    """ grape runHook

    Usage: grape-runHook
           grape-runHook pre-commit [--noExit]
           grape-runHook pre-push <dest> <url> [--noExit]
           grape-runHook pre-rebase <basebranch> [<rebasebranch>] [--noExit]
           grape-runHook post-commit [--autopush=<bool>] [--cascade=<pairs>] [--noExit]
           grape-runHook post-rebase [--rebaseSubmodule=<bool>] [--noExit]
           grape-runHook post-merge <wasSquashed> [--mergeSubmodule=<bool>] [--noExit]
           grape-runHook post-checkout <prevHEAD> <newHEAD> <isBranchCheckout> [--checkoutSubmodule=<bool>] [--noExit]

    Options:
        --autopush=<bool>           autopushes commits to origin
                                    [default: .grapeconfig.post-commit.autopush]
        --cascade=<pairs>           performs a post commit cascade
                                    [default: .grapeconfig.post-commit.cascade]
        --rebaseSubmodule=<bool>    [default: .grapeconfig.post-rebase.submoduleUpdate]
        --mergeSubmodule=<bool>     [default: .grapeconfig.post-merge.submoduleUpdate]
        --checkoutSubmodule=<bool>  [default: .grapeconfig.post-checkout.submoduleUpdate
        --noExit                    Normally runhook returns by calling exit(0). With this flag, returns by returning
                                    True.

    Arguments:
        <dest>                      (pre-push only) The destination repo.
        <url>                       (pre-push only) The destination's URL.
        <basebranch>                (pre-rebase only) The upstream commit this branch was forked from.
        <rebasebranch>              (pre-rebase only) The branch being rebased (empty when rebasing current branch)
        <wasSquashed>               (post-merge only) Status flag indicating whether the merge was a squash merge.



    """

    def __init__(self):
        super(RunHook, self).__init__()
        self._key = "runHook"
        self._section = "Hooks"
        self.commands = {"pre-commit": self.preCommit,
                         "post-commit": self.postCommit,
                         "pre-push": self.prePush,
                         "pre-rebase": self.preRebase,
                         "post-rebase": self.postRebase,
                         "post-merge": self.postMerge,
                         "post-checkout": self.postCheckout}

    def description(self):
        return "Runs a grape hook"

    def execute(self, args):
        for command in args.keys():
            if command in self.commands.keys():
                if args[command]:
                    try:
                        args['execution_path'] = self.command_path
                        self.commands[command](args)
                    except KeyError:
                        pass
                    finally:
                        if args["--noExit"]:
                            return True
                        else:
                            exit(0)

    def setDefaultConfig(self, config):
        # post-commit
        try:
            config.add_section('post-commit')
        except configparser.DuplicateSectionError:
            pass
        config.set('post-commit', 'autopush', 'False')
        config.set('post-commit', 'cascade', 'None')

        # post-rebase
        try:
            config.add_section('post-rebase')
        except configparser.DuplicateSectionError:
            pass
        config.set('post-rebase', 'submoduleUpdate', 'False')

        # post-merge
        try:
            config.add_section('post-merge')
        except configparser.DuplicateSectionError:
            pass
        config.set('post-merge', 'submoduleUpdate', 'False')

        #post-checkout
        try:
            config.add_section('post-checkout')
        except configparser.DuplicateSectionError:
            pass
        config.set('post-checkout', 'submoduleUpdate', 'False')

    @staticmethod
    def postCommit(args):
        #applies the autoPush hook
        autoPush = args["--autopush"]
        if autoPush.lower().strip() != "false":
            try:
                git.push("-u origin HEAD", self.command_path)
            except grape_errors.GrapeGitError:
                pass
            autoPush = True
        else:
            autoPush = False
        #applies the cascade hook
        logging.info("GRAPE: checking for cascades...")
        cascadeDict = config_parser_base.GrapeConfigParserBase.parseConfigPairList(args["--cascade"])
        if cascadeDict:
            currentBranch = git.currentBranch(self.command_path)
            while currentBranch in cascadeDict:
                source = currentBranch
                target = cascadeDict[source]
                fastForward = False
                logging.info(f"GRAPE: Cascading commit from {source} to {target}...")
                if git.branchUpToDateWith(source, target):
                    fastForward = True
                    logging.info("GRAPE: should be a fastforward cascade...")
                git.checkout(f"{target}", self.command_path)
                git.merge(f"{source} -m 'Cascade from {source} to {target}'", self.command_path)
                # we need to kick off the next one if it was a fast forward merge.
                # otherwise, another post-commit hook should be called from the merge commit.
                if fastForward:
                    if autoPush:
                        git.push(f"origin {target}", self.command_path)
                        logging.info("GRAPE: auto push done")
                    currentBranch = target
                else:
                    currentBranch = None


    def preCommit(self, args):
        pass

    def prePush(self, args):
        pass

    def preRebase(self, args):
        pass

    @staticmethod
    def postRebase(args, *, execution_path):
        updateSubmodule = args["--rebaseSubmodule"]
        if updateSubmodule and updateSubmodule.lower() == 'true':
            git.submodule("--quiet sync", execution_path=execution_path)
            git.submodule("update --rebase", execution_path=execution_path)

    @staticmethod
    def postMerge(args, *, execution_path):
        updateSubmodule = args["--mergeSubmodule"]
        if updateSubmodule and updateSubmodule.lower() == 'true':
            logging.info("Post-Merge Hook: Syncing submodule URLs...")
            git.submodule("--quiet sync", execution_path=execution_path)
            logging.info("Post-Merge Hook: Updating submodules...")
            git.submodule("--quiet update --merge", execution_path=execution_path)

    @staticmethod
    def postCheckout(args, *, execution_path):
        updateSubmodule = args["--checkoutSubmodule"]
        if updateSubmodule and updateSubmodule.lower() == 'true':
            logging.info("Post-Checkout Hook: Syncing submodule URLs...")
            git.submodule("--quiet sync", execution_path=execution_path)
            logging.info("Post-Checkout Hook: Updating submodules...")
            git.submodule("--quiet update", execution_path=execution_path)
