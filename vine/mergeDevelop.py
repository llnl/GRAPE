import os
import sys
import ConfigParser
import grape_errors
import grapeGit as git
import checkout
import config_parser_global
import config_parser_user
from option import Option
import resumable
import vine_logging
import utility


# pull and merge in an up-to-date development branch
class MergeDevelop(resumable.Resumable, Option):
    """
    grape md  (Merge Down)
    merge changes from a public branch into your current topic branch
    If executed on a public branch, performs a pull --rebase to update your local public branch.
    Usage: grape-md [--public=<branch>] [--subpublic=<branch>]
                    [--am | --as | --at | --aT | --ay | --aY | --ask | --askAll]
                    [--continue]
                    [--recurse | --noRecurse]
                    [--noUpdate]
                    [--squash]


    Options:
        --public=<branch>       Overrides the public branch to merge from.
                                Default behavior is to merge according to
                                .grapeconfig.flow.topicPrefixMappings.
        --subpublic=<branch>    Overrides the submodules' public branch to merge from. Default behavior is to merge
                                according to .grapeconfig.flow.submoduleTopicPrefixMappings.
        --am                    Perform the merge using git's default strategy. (default)
        --as                    Perform the merge issuing conflicts on any file modified by both branches.
        --at                    Perform the merge using the public branch's version for any file modified by both branches.
        --aT                    Perform the merge resolving conficts using the public branch's version.
        --ay                    Perform the merge using the your topic branch's version for any file modified by both branches.
        --aY                    Perform the merge resolving conflicts using your topic branch's version.
        --ask                   Ask to determine the merge strategy.
        --askAll                Ask to determine the merge strategy before merging each subproject.
        --recurse               Perform merges in submodules first, then merge in the outer level keeping the
                                results of submodule merges.
        --noRecurse             Do not perform merges in submodules, just attempt to merge the gitlinks.
        --continue              Resume the most recent call to grape md that issued conflicts in this workspace.
        --noUpdate              Do not update local versions of the public branch before attempting merges.
        --squash                Perform squash merges.



    """
    def __init__(self):
        super(MergeDevelop, self).__init__()
        self._key = "md"
        self._section = "Merge"

    @staticmethod
    def lookupPublicBranch():
        config = config_parser_global.grapeConfig()
        try:
            currentBranch = git.currentBranch()
        except grape_errors.GrapeGitError:
            return 'unknown'
        if currentBranch in config.get(Option.SECTION_FLOW, 'publicBranches'):
            return currentBranch
        try:
            branch = config.getPublicBranchFor(currentBranch)
        except KeyError:
            branchPrefix = git.branchPrefix(currentBranch)
            print("WARNING: prefix %s does not have an associated topic branch, nor is a default"
                  "public branch configured. \n"
                  "use --public=<branch> to define, or add %s:<branch> or ?:<branch> to \n"
                  "[flow].publicBranches in your .grapeconfig or .git/.grapeuserconfig. " % (branchPrefix, branchPrefix))
            branch = None
        return branch

    def description(self):
        try:
            currentBranch = git.currentBranch()
        except grape_errors.GrapeGitError:
            currentBranch = 'unknown'
        publicBranch = self.lookupPublicBranch()

        return "Merge latest changes on %s into %s" % (publicBranch, currentBranch)


    def execute(self, args):
        # Imported here to avoid circular dependencies
        import grapeMenu

        if not "<<cmd>>" in args:
            args["<<cmd>>"] = "md"
        branch = args["--public"]
        if not branch:
            branch = config_parser_global.grapeConfig().getPublicBranchFor(git.currentBranch())
            if not branch:
                vine_logging.printMsg("ERROR: public branches must be configured for grape md to work.")
        args["--public"] = branch

        # check to see if we already have the branch
        try:
            git.shortSHA(branch)
        except:
            # stripping of origin/ from the branch specification
            if branch.startswith("origin/"):
                basebranch = branch[len("origin/"):]
            else:
                basebranch = branch
            # see if the branch exists locally
            try:
                git.shortSHA(basebranch)
            except:
                # otherwise fetch it
                git.fetch("origin", "%s:%s" % (basebranch, basebranch))

        # determine whether to merge in subprojects that have changed
        try:
            submodules = self.progress["submodules"]
        except KeyError:
            modifiedSubmodules = git.getModifiedSubmodules(utility.workspaceDir(), branch, git.currentBranch())
            activeSubmodules = git.getActiveSubmodules(utility.workspaceDir())
            submodules = [sub for sub in modifiedSubmodules if sub in activeSubmodules]

        try:
            nested = self.progress["nested"]
        except KeyError:
            nested = config_parser_user.getAllActiveNestedSubprojectPrefixes()

        config = config_parser_global.grapeConfig()
        recurse = config.getboolean(Option.SECTION_WORKSPACE, "manageSubmodules") or args["--recurse"]
        recurse = recurse and (not args["--noRecurse"]) and len(submodules) > 0
        args["--recurse"] = recurse

        # if we stored cwd in self.progress, make sure we end up there
        if "cwd" in self.progress:
            cwd = self.progress["cwd"]
        else:
            cwd = utility.workspaceDir()
        os.chdir(cwd)

        if "conflictedFiles" in self.progress:
            conflictedFiles = self.progress["conflictedFiles"]
        else:
            conflictedFiles = []

        # take note of whether all submodules are currently present, assume user wants to add any new submodules to WS if so
        activeSubmodulesCheck0 = git.getActiveSubmodules(utility.workspaceDir())

        self.progress["allActive"] = set(git.getAllSubmodules()) == set(git.getActiveSubmodules(utility.workspaceDir()))

        # checking for a consistent workspace before doing a merge
        vine_logging.printMsg("Checking for a consistent workspace before performing merge...")
        ret = grapeMenu.menu().applyMenuChoice("status", ['--failIfInconsistent'])
        if ret is False:
            vine_logging.printMsg("Workspace inconsistent! Aborting attempt to do the merge. Please address above issues and then try again.")
            return False

        if not "updateLocalDone" in self.progress and not args["--noUpdate"]:
            # make sure public branches are to date in outer level repo.
            vine_logging.printMsg("Calling grape up to ensure topic and public branches are up-to-date. ")
            grapeMenu.menu().applyMenuChoice('up', ['up','--public=%s' % args["--public"]])
            self.progress["updateLocalDone"] = True

        addedModules = []
        removedModules = []
        changedURLModules = []
        if recurse:
            checkout.parseGitModulesDiffOutput(git.currentBranch(), branch, addedModules, removedModules, changedURLModules)
            # deinit and clean out any submodules that changed urls
            for sub in changedURLModules:
                vine_logging.printMsg("url for %s changed, attempting to remove references for %s submodule before merge." % (sub, "active" if sub in activeSubmodulesCheck0 else "inactive"))
                cleaned = checkout.cleanSubmodule(sub, args, True, activeSubmodulesCheck0)
                if not cleaned:
                    vine_logging.printMsg("Failed to remove old submodule for %s." % sub)
                    return False

        # do an outer merge if we haven't done it yet
        if not "outerLevelDone" in self.progress:
            self.progress["outerLevelDone"] = False
        if not self.progress["outerLevelDone"]:
            conflictedFiles = self.outerLevelMerge(args, branch)

        # get active submodules post-merge
        reinitActiveSubmodulesCheck = git.getActiveSubmodules(utility.workspaceDir())
        # add in active submodules pre-merge
        reinitActiveSubmodulesCheck.extend(activeSubmodulesCheck0)

        reinitModules = changedURLModules + addedModules
        # reinit and create the current branch in any submodules with changed URLs
        # or new submodules from the merge (usually these new submodules will be inactive,
        # but they could be active if it was in the workspace already).
        if reinitModules and reinitActiveSubmodulesCheck:
            currentBranch = git.currentBranch()
            submapping = config.getMapping(Option.SECTION_WORKSPACE, 'submodulepublicmappings')
            try:
                submodulePubBranch = submapping[args["--public"]]
            except:
                submodulePubBranch = args["--public"]
            for sub in reinitModules:
                if sub in reinitActiveSubmodulesCheck:
                    os.chdir(utility.workspaceDir())
                    git.submodule("update --init %s" % sub)
                    os.chdir(os.path.join(utility.workspaceDir(), sub))
                    # fetch the public branch so there is a branch to merge from
                    git.fetch("origin %s:%s" % (submodulePubBranch, submodulePubBranch))
                    # If there is already a branch by this name in the new repo,
                    # this will reset the branch.
                    git.checkout("-B %s HEAD" % currentBranch)

            os.chdir(utility.workspaceDir())

        # outerLevelMerge returns False if there was a non-conflict related issue
        if conflictedFiles is False:
            vine_logging.printMsg("Initial merge failed. Resolve issue and try again. ")
            return False

        # merge nested subprojects
        for subproject in nested:
            if not self.mergeSubproject(args, subproject, branch, nested, cwd, isSubmodule=False):
                # stop for user to resolve conflicts
                self.progress["nested"] = nested
                self.dumpProgress(args)
                os.chdir(cwd)
                return False
        os.chdir(cwd)

        # merge submodules
        if recurse:
            if len(submodules) > 0:
                if args["--subpublic"]:
                    # respect the callers wishes (usually this is grape m , mr, or pull)
                    subPublic = args["--subpublic"]
                else:
                    # default is to merge the submodule branch that is mapped to the public branch
                    subBranchMappings = config.getMapping(Option.SECTION_WORKSPACE, "submodulePublicMappings")
                    subPublic = subBranchMappings[config.getPublicBranchFor(branch)]
                for submodule in submodules:
                    if not self.mergeSubproject(args, submodule, subPublic, submodules, cwd, isSubmodule=True):
                        # stop for user to resolve conflicts
                        self.progress["conflictedFiles"] = conflictedFiles
                        self.dumpProgress(args)
                        return False
                os.chdir(cwd)
                conflictedFiles = git.conflictedFiles()
                # now that we resolved the submodule conflicts, continue the outer level merge
                if len(conflictedFiles) == 0:
                    self.continueLocalMerge(args)
                    conflictedFiles = git.conflictedFiles()




        if conflictedFiles:
            self.progress["stopPoint"] = "resolve conflicts"
            self.progress["cwd"] = cwd
            self.dumpProgress(args, "GRAPE: Outer level merge generated conflicts. Please resolve using git mergetool "
                                    "and then \n continue by calling 'grape md --continue' .")
            return False
        else:
            grapeMenu.menu().applyMenuChoice("runHook", ["post-merge", '0', "--noExit"])

        # ensure all submodules are currently present in WS if all submodules were present at the beginning of merge
        if self.progress["allActive"]:
            activeSubmodulesCheck1 = git.getActiveSubmodules(utility.workspaceDir())
            if (set(activeSubmodulesCheck0) != set(activeSubmodulesCheck1)):
                vine_logging.printMsg("Updating new submodules using grape uv --allSubmodules")
                grapeMenu.menu().applyMenuChoice("uv", ["--allSubmodules", "--skipNestedSubprojects"])

        return True


    def mergeSubproject(self, args, subproject, subPublic, subprojects, cwd, isSubmodule=True):
        # if we did this merge in a previous run, don't do it again
        try:
            if self.progress["Subproject: %s" % subproject] == "finished":
                return True
        except KeyError:
            pass
        os.chdir(os.path.join(git.baseDir(), subproject))
        mergeArgs = args.copy()
        mergeArgs["--public"] = subPublic

        vine_logging.printMsg("Merging %s into %s for %s %s" %
                         (subPublic, git.currentBranch(), "submodule" if isSubmodule else "subproject", subproject))
        git.fetch("origin")
        # update our local reference to the remote branch so long as it's fast-forwardable or we don't have it yet..)
        hasRemote = git.hasBranch("origin/%s" % subPublic)
        hasBranch = git.hasBranch(subPublic)
        if  hasRemote and  (git.branchUpToDateWith(subPublic, "origin/%s" % subPublic) or not hasBranch):
            git.fetch("origin %s:%s" % (subPublic, subPublic))
        ret = self.mergeIntoCurrent(subPublic, mergeArgs, subproject)
        # skip nested subprojects that fail to merge
        if not ret and not isSubmodule and not git.conflictedFiles():
            vine_logging.printMsg("Unable to merge subproject {0}, skipping...".format(subproject))
            ret = True
        conflict = not ret
        if conflict:
            self.progress["stopPoint"] = "Subproject: %s" % subproject
            subprojectKey = "submodules" if isSubmodule else "nested"
            self.progress[subprojectKey] = subprojects
            self.progress["cwd"] = cwd
            conflictedFiles = git.conflictedFiles()
            if conflictedFiles:
                if isSubmodule:
                    typeStr = "submodule"
                else:
                    typeStr = "nested subproject"

                vine_logging.printMsg("Merge in %s %s from %s to %s issued conflicts. Resolve and commit those changes \n"
                                 "using git mergetool and git commit in the submodule, then continue using grape\n"
                                 "%s --continue" % (typeStr, subproject, subPublic, git.currentBranch(), args["<<cmd>>"]))
            else:
                vine_logging.printMsg("Merge in %s failed for an unhandled reason. You may need to stash / commit your current\n"
                                 "changes before doing the merge. Inspect git output above to troubleshoot. Continue using\n"
                                 "grape %s --continue." % (subproject, args["<<cmd>>"]))
            return False
        # if we are resuming from a conflict, the above grape m call would have taken care of continuing.
        # clear out the --continue flag.
        args["--continue"] = False
        # stage the updated submodule
        os.chdir(cwd)
        if isSubmodule:
            git.add(subproject)
        self.progress["Subproject: %s" % subproject] = "finished"
        return True

    def outerLevelMerge(self, args, branch):
        vine_logging.printMsg("Merging changes from %s into your current branch..." % branch)

        conflict = not self.mergeIntoCurrent(branch, args, "outer level project")

        if conflict:
            conflictedFiles = git.conflictedFiles()
            if conflictedFiles:
                return conflictedFiles
            else:
                vine_logging.printMsg("Merge issued error, but no conflicts. Aborting...")
                return False
        else:
            self.progress["outerLevelDone"] = True
            return []

    def merge(self, branch, strategy, args):
        squashArg = "--squash" if args["--squash"] else ""
        try:
            git.merge("%s %s %s" % (squashArg, branch, strategy))
            return True
        except grape_errors.GrapeGitError as error:
            print error.gitOutput
            if "conflict" in error.gitOutput.lower():
                if args['--at'] or args['--ay']:
                    if args['--at']:
                        vine_logging.printMsg("Resolving conflicted files by accepting changes from %s." % branch)
                        checkoutArg = "--theirs"
                    else:
                        vine_logging.printMsg("Resolving conflicted files by accepting changes from your branch.")
                        checkoutArg = "--ours"
                    try:
                        path = git.baseDir()
                        git.checkout("%s %s" % (checkoutArg, path))
                        git.add("%s" % path)
                        git.commit("-m 'Resolve conflicts using %s'" % checkoutArg)
                        return True
                    except grape_errors.GrapeGitError as resolveError:
                        print resolveError.gitOutput
                        return False
                else:
                    vine_logging.printMsg("Conflicts generated. Resolve using git mergetool, then continue "
                                     "with grape %s --continue. " % args["<<cmd>>"])
                    return False
            else:
                print("Merge command %s failed. Quitting." % error.gitCommand)
                return False

    def continueLocalMerge(self, args):
        # "utility.userInput" is a function
        git.fixActiveSubmodules(utility.workspaceDir(), utility.userInput)
        status = git.status()
        # Commit after conflict resolution.
        # If there were no conflicts in the outer-level repo, we still need to commit the submodule gitlinks.
        if "All conflicts fixed but you are still merging." in status or \
           (not "You have unmerged paths." in status and "Changes to be committed:" in status):
            git.commit("-m \"GRAPE: merge from %s after conflict resolution.\"" % args["--public"])
            return True
        else:
            return False

    def mergeIntoCurrent(self, branchName, args, projectName):
        choice = False
        strategy = 'am' 
        if args["--continue"]:
            if self.continueLocalMerge(args):
                return True
        if args['--am']:
            strategy = 'am'
        elif args['--as']:
            strategy = 'as'
        elif args['--at']:
            strategy = 'at'
        elif args['--aT']:
            strategy = 'aT'
        elif args['--ay']:
            strategy = 'ay'
        elif args['--aY']:
            strategy = 'aY'

        if args['--ask'] or args['--askAll']:
            repoSpec = " in %s" % projectName if args['--askAll'] else ""
            strategy = utility.userInput("How do you want to resolve changes%s? [am / as / at / aT / ay / aY] \n" % repoSpec +
                                         "am: Auto Merge (default) \n" +
                                         "as: Safe Merge - issues conflicts if both branches touch same file.\n" +
                                         "at: Accept Theirs - accept changes in %s if both branches touch same file\n" % branchName +
                                         "aT: Accept Theirs (if conflicted) - resolves conflicts by accepting changes in %s\n" % branchName +
                                         "ay: Accept Yours - accept changes in current branch if both branches touch same file\n" +
                                         "aY: Accept Yours (if conflicted) - resolves conflicts by using changes in current branch.",
                                         "am")

        if strategy == 'am':
            args["--am"] = True
            vine_logging.printMsg("Merging using git's default strategy...")
            choice = self.merge(branchName, "", args)
        elif strategy == 'as' or strategy == 'at' or strategy == 'ay':
            if strategy == 'as':
                args["--as"] = True
                # this employs using the custom low-level merge driver "verify" and
                # appending a "* merge=verify" to the .gitattributes file.
                #
                # see
                # http://stackoverflow.com/questions/5074452/git-how-to-force-merge-conflict-and-manual-merge-on-selected-file
                # for details.
                vine_logging.printMsg("Merging forcing conflicts whenever both branches edited the same file...")
            elif strategy == 'at':
                args["--at"] = True
            elif strategy == 'ay':
                args["--ay"] = True
            base = git.gitDir()
            if base == "":
                return False
            attributes = os.path.join(base, ".gitattributes")
            tmpattributes = None
            if os.path.exists(attributes):
                tmpattributes = os.path.join(base, ".gitattributes.tmp")
                # save original attributes file
                shutil.copyfile(attributes, tmpattributes)
                #append merge driver strategy to the attributes file
                with open(attributes, 'a') as f:
                    f.write("* merge=verify")
            else:
                with open(attributes, 'w') as f:
                    f.write("* merge=verify")

            # perform the merge
            choice = self.merge(branchName, "", args)

            # restore original attributes file
            if tmpattributes:
                shutil.copyfile(tmpattributes, attributes)
                os.remove(tmpattributes)
            else:
                os.remove(attributes)
        elif strategy == 'aT':
            args["--aT"] = True
            vine_logging.printMsg("Merging using recursive strategy, resolving conflicts cleanly with changes in %s..." % branchName)
            choice = self.merge(branchName, "-Xtheirs", args)
        elif strategy == 'aY':
            args["--aY"] = True
            vine_logging.printMsg("Merging using recursive strategy, resolving conflicts cleanly with current branch's changes...")
            choice = self.merge(branchName, "-Xours", args)

        return choice

    def setDefaultConfig(self, config):
        try:
            config.add_section(self.SECTION_FLOW)
        except ConfigParser.DuplicateSectionError:
            pass
        config.set(self.SECTION_FLOW, "publicBranches", "develop master")
        config.set(self.SECTION_FLOW, "topicPrefixMappings", "?:develop")
        config.set(self.SECTION_FLOW, "topicDestinationMappings", "none")

    def _resume(self, args):
        super(MergeDevelop, self)._resume(args)
        if self.progress["stopPoint"] == "public rebase":
            # recover from conflicts by continuing the rebase
            git.rebase("--continue")
            retval = True
        else:
            retval = self.execute(args)
        return retval

    def _saveProgress(self, args):
        super(MergeDevelop, self)._saveProgress(args)
        # this lets grape m know that the --continue is for grape md to resume...
        self.progress["inMD"] = True
