import option, sys, utility, os
import grapeGit as git
import ConfigParser
import grapeConfig

#option that installs wrapper calls to grape as git hooks in this repo.
class InstallHooks(option.Option):
    """ grape installHooks
    Installs callbacks to grape in .git/hooks, allowing grape-configurable hooks to be used
    in this repo.

    Usage: grape-installHooks [--toInstall=<hook>]...

    Options:
    --toInstall=<hook>    the list of hook-types to install
                          [default: pre-commit pre-push pre-rebase post-commit post-rebase post-merge post-checkout]

    """
    def __init__(self):
        self._key = "installHooks"
        self._section = "Hooks"

    def description(self):
        return "Installs grape as your hook manager for this repo. \n\t\t(May overwrite existing hooks you have installed in this repo)"

    def execute(self,args):
        os.chdir(os.path.join(git.gitDir(),"hooks"))
        hooks = args["--toInstall"]
        for h in hooks:
            with open(h,'w') as f:
                f.write("#!/bin/sh\n")
                grapeCmd = utility.getGrapeExec()
                f.write("%s runHook %s \"$@\" \n" % (grapeCmd,h))
            os.chmod(h,0755)
        return True

    def setDefaultConfig(self, config):
        pass

class RunHook(option.Option):
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
        self._key = "runHook"
        self._section = "Hooks"
        self.commands = {"pre-commit":self.preCommit,
                    "post-commit":self.postCommit,
                    "pre-push":self.prePush,
                    "pre-rebase":self.preRebase,
                    "post-rebase":self.postRebase,
                    "post-merge":self.postMerge,
                    "post-checkout":self.postCheckout}

    def description(self):
        return "Runs a grape hook"

    def execute(self,args):
        for command in args.keys():
            try:
                if args[command]:
                    self.commands[command](args)
            except KeyError:
                pass
        if args["--noExit"]:
            return True
        else:
            exit(0)

    def setDefaultConfig(self,config):
        # post-commit
        try:
            config.add_section('post-commit')
        except ConfigParser.DuplicateSectionError:
            pass
        config.set('post-commit','autopush','False')
        config.set('post-commit','cascade','None')

        # post-rebase
        try:
            config.add_section('post-rebase')
        except ConfigParser.DuplicateSectionError:
            pass
        config.set('post-rebase','submoduleUpdate','False')

        # post-merge
        try:
            config.add_section('post-merge')
        except ConfigParser.DuplicateSectionError:
            pass
        config.set('post-merge','submoduleUpdate','False')

        #post-checkout
        try:
            config.add_section('post-checkout')
        except ConfigParser.DuplicateSectionError:
            pass
        config.set('post-checkout','submoduleUpdate','False')


    def postCommit(self,args):
        #applies the autoPush hook
        autoPush = args["--autopush"]
        if autoPush.lower().strip() != "false":
            try:
                git.push("-u origin HEAD")
            except:
                pass
            autoPush = True
        else:
            autoPush = False
        #applies the cascade hook
        cascadeDict = grapeConfig.GrapeConfigParser.parseConfigPairList(args["--cascade"])
        if cascadeDict:
            currentBranch = git.currentBranch()
            while currentBranch in cascadeDict:
                source = currentBranch
                target = cascadeDict[source]
                fastForward = False
                print("GRAPE: Cascading commit from %s to %s..." % (source,target))
                if git.branchUpToDateWith(source,target):
                    fastForward = True
                    print("GRAPE: should be a fastforward cascade...")
                git.checkout("%s" % target)
                git.merge("%s -m 'Cascade from %s to %s'" % (source,source,target))
                # we need to kick off the next one if it was a fast forward merge.
                # otherwise, another post-commit hook should be called from the merge commit.
                if fastForward:
                    if autoPush:
                        git.push("origin %s" % target)
                    currentBranch = target
                else:
                    currentBranch = None


    def preCommit(self, args):
        pass

    def prePush(self, args):
        pass

    def preRebase(self, args):
        pass

    def postRebase(self, args):
        updateSubmodule = args["--rebaseSubmodule"]
        if updateSubmodule and updateSubmodule.lower() == 'true':
            git.submodule("sync")
            git.submodule("update --rebase")

    def postMerge(self, args):
        updateSubmodule = args["--mergeSubmodule"]
        if updateSubmodule and updateSubmodule.lower() == 'true':
            git.submodule("sync")
            git.submodule("update --merge")

    def postCheckout(self, args):
        updateSubmodule = args["--checkoutSubmodule"]
        if updateSubmodule and updateSubmodule.lower() == 'true':
            git.submodule("sync")
            git.submodule("update")






