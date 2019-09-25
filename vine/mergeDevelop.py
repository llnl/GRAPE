import configparser
import io
import logging
import os
import sys
from vine import checkout
from vine import config_parser_global
from vine import config_parser_user
from vine import grape_errors
from vine import grapeGit as git
from vine import utility
from vine import vine_logging
from vine.command_path_handler import CommandPathHandler
from vine.option import Option
from vine.resumable import Resumable
from vine.vine_logging import log_wrapper


# pull and merge in an up-to-date development branch
class MergeDevelop(Resumable, Option, CommandPathHandler):
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
    def lookupPublicBranch(*, execution_path):
        config = config_parser_global.grapeConfig()
        try:
            currentBranch = git.currentBranch(execution_path=execution_path)
        except grape_errors.GrapeGitError:
            return 'unknown'
        if currentBranch in config.get(Option.SECTION_FLOW, 'publicBranches'):
            return currentBranch
        try:
            branch = config.getPublicBranchFor(currentBranch)
        except KeyError:
            branchPrefix = git.branchPrefix(currentBranch)
            logging.warning(f"WARNING: prefix {branchPrefix} does not have " +
                  "an associated topic branch, nor is a default public " +
                  "branch configured. \nuse --public=<branch> to define, " +
                  f"or add {branchPrefix}:<branch> or ?:<branch> to " +
                  "\n[flow].publicBranches in your .grapeconfig or " +
                  ".git/.grapeuserconfig. ")
            branch = None
        return branch

    def description(self):
        try:
            currentBranch = git.currentBranch(execution_path=self.command_path)
        except grape_errors.GrapeGitError:
            currentBranch = 'unknown'
        publicBranch = self.lookupPublicBranch(self.command_path)

        return "Merge latest changes on {publicBranch} into {currentBranch}"

    @log_wrapper
    def execute(self, args):
        # Imported here to avoid circular dependencies
        from vine import grapeMenu

        self.set_progress_file(execution_path=self.command_path)

        if not "<<cmd>>" in args:
            args["<<cmd>>"] = "md"
        branch = args["--public"]
        if not branch:
            branch = config_parser_global.grapeConfig().getPublicBranchFor(git.currentBranch(execution_path=self.command_path))
            if not branch:
                logging.error("ERROR: public branches must be configured for grape md to work.")
        args["--public"] = branch

        # check to see if we already have the branch
        try:
            git.shortSHA(branch, execution_path=self.command_path)
        except:
            # stripping of origin/ from the branch specification
            if branch.startswith("origin/"):
                basebranch = branch[len("origin/"):]
            else:
                basebranch = branch
            # see if the branch exists locally
            try:
                git.shortSHA(basebranch, execution_path=self.command_path)
            except:
                # otherwise fetch it
                git.fetch("origin", f"{basebranch}:{basebranch}",
                          execution_path=self.command_path)

        # determine whether to merge in subprojects that have changed
        if "submodules" in self.progress:
            submodules = self.progress["submodules"]
        else:
            modifiedSubmodules = git.getModifiedSubmodules(self.workspace_dir, branch, git.currentBranch(execution_path=self.command_path))
            activeSubmodules = git.getActiveSubmodules(execution_path=self.workspace_dir)
            submodules = [sub for sub in modifiedSubmodules if sub in activeSubmodules]

        nested = getattr(self.progress, 'nested', config_parser_user.getAllActiveNestedSubprojectPrefixes(workspaceDir=self.workspace_dir))

        config = config_parser_global.grapeConfig()
        recurse = config.getboolean(Option.SECTION_WORKSPACE, "manageSubmodules") or args["--recurse"]
        recurse = recurse and (not args["--noRecurse"]) and len(submodules) > 0
        args["--recurse"] = recurse

        # if we stored cwd in self.progress, make sure we end up there
        if "cwd" in self.progress:
            cwd = self.progress["cwd"]
            self.command_path = cwd
        else:
            cwd = self.workspace_dir

        if "conflictedFiles" in self.progress:
            conflictedFiles = self.progress["conflictedFiles"]
        else:
            conflictedFiles = []

        # take note of whether all submodules are currently present, assume user wants to add any new submodules to WS if so
        activeSubmodulesCheck0 = git.getActiveSubmodules(execution_path=self.workspace_dir)

        self.progress["allActive"] = set(git.getAllSubmodules(execution_path=self.workspace_dir)) == set(git.getActiveSubmodules(execution_path=self.workspace_dir))

        # checking for a consistent workspace before doing a merge
        logging.info("Checking for a consistent workspace before performing merge...")
        menu = grapeMenu.menu()
        menu.set_command_path(self.command_path)
        ret = menu.applyMenuChoice("status", ['--failIfInconsistent'])
        if ret is False:
            logging.error("Workspace inconsistent! Aborting attempt to do the merge. Please address above issues and then try again.")
            return False

        if not "updateLocalDone" in self.progress and not args["--noUpdate"]:
            # make sure public branches are to date in outer level repo.
            logging.info("Calling grape up to ensure topic and public branches are up-to-date. ")
            menu.applyMenuChoice('up', ['up', f'--public={args["--public"]}'])
            self.progress["updateLocalDone"] = True

        addedModules = []
        removedModules = []
        changedURLModules = []
        if recurse:
            checkout.parseGitModulesDiffOutput(
                git.currentBranch(execution_path=self.command_path), branch, addedModules,
                removedModules, changedURLModules,
                execution_path=self.command_path)
            # deinit and clean out any submodules that changed urls
            for sub in changedURLModules:
                is_active = "active" if sub in activeSubmodulesCheck0 else "inactive"
                logging.info(
                    f"url for {sub} changed, attempting to remove " +
                    f"references for {is_active} submodule before merge.")
                cleaned = checkout.cleanSubmodule(sub, args, True, activeSubmodulesCheck0, workspace_dir=self.workspace_dir)
                if not cleaned:
                    logging.warning(f"Failed to remove old submodule for {sub}.")
                    return False

        # do an outer merge if we haven't done it yet
        if not "outerLevelDone" in self.progress:
            self.progress["outerLevelDone"] = False
        if not self.progress["outerLevelDone"]:
            conflictedFiles = self.outerLevelMerge(args, branch)

        # get active submodules post-merge
        reinitActiveSubmodulesCheck = git.getActiveSubmodules(execution_path=self.workspace_dir)
        # add in active submodules pre-merge
        reinitActiveSubmodulesCheck.extend(activeSubmodulesCheck0)

        reinitModules = changedURLModules + addedModules
        # reinit and create the current branch in any submodules with changed URLs
        # or new submodules from the merge (usually these new submodules will be inactive,
        # but they could be active if it was in the workspace already).
        if reinitModules and reinitActiveSubmodulesCheck:
            currentBranch = git.currentBranch(execution_path=self.command_path)
            submapping = config.getMapping(Option.SECTION_WORKSPACE, 'submodulepublicmappings')
            try:
                submodulePubBranch = submapping[args["--public"]]
            except:
                submodulePubBranch = args["--public"]
            for sub in reinitModules:
                if sub in reinitActiveSubmodulesCheck:
                    git.submodule(f"update --init {sub}", execution_path=self.workspace_dir)
                    sub_dir = os.path.join(self.workspace_dir, sub)
                    # fetch the public branch so there is a branch to merge from
                    git.fetch(f"origin {submodulePubBranch}:{submodulePubBranch}",
                              execution_path=sub_dir)
                    # If there is already a branch by this name in the new repo,
                    # this will reset the branch.
                    git.checkout(f"-B {currentBranch} HEAD",
                                 execution_path=sub_dir)

        # outerLevelMerge returns False if there was a non-conflict related issue
        if conflictedFiles is False:
            logging.warning("Initial merge failed. Resolve issue and try again. ")
            return False

        # merge nested subprojects
        for subproject in nested:
            if not self.mergeSubproject(args, subproject, branch, nested, cwd, isSubmodule=False):
                # stop for user to resolve conflicts
                self.progress["nested"] = nested
                self.dumpProgress(args)
                return False

        # merge submodules
        if recurse and len(submodules) > 0:
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
            conflictedFiles = git.conflictedFiles(execution_path=cwd)
            # now that we resolved the submodule conflicts, continue the outer level merge
            if len(conflictedFiles) == 0:
                self.continueLocalMerge(args)
                conflictedFiles = git.conflictedFiles(execution_path=cwd)

        if conflictedFiles:
            self.progress["stopPoint"] = "resolve conflicts"
            self.progress["cwd"] = cwd
            self.dumpProgress(args, "GRAPE: Outer level merge generated conflicts. Please resolve using git mergetool "
                                    "and then \n continue by calling 'grape md --continue' .")
            return False
        else:
            menu.applyMenuChoice("runHook", ["post-merge", '0', "--noExit"])

        # ensure all submodules are currently present in WS if all submodules were present at the beginning of merge
        if self.progress["allActive"]:
            activeSubmodulesCheck1 = git.getActiveSubmodules(execution_path=self.workspace_dir)
            if (set(activeSubmodulesCheck0) != set(activeSubmodulesCheck1)):
                logging.info("Updating new submodules using grape uv --allSubmodules")
                menu.applyMenuChoice("uv", ["--allSubmodules", "--skipNestedSubprojects"])

        return True


    def mergeSubproject(self, args, subproject, subPublic, subprojects, cwd, isSubmodule=True):
        # if we did this merge in a previous run, don't do it again
        try:
            if self.progress[f"Subproject: {subproject}"] == "finished":
                return True
        except KeyError:
            pass
        execution_path = os.path.join(
            git.baseDir(execution_path=self.command_path), subproject)
        mergeArgs = args.copy()
        mergeArgs["--public"] = subPublic

        submodule_or_subproject = "submodule" if isSubmodule else "subproject"
        logging.info(f"Merging {subPublic} into {git.currentBranch(execution_path=self.command_path)} " +
                     f"for {submodule_or_subproject} {subproject}")
        git.fetch("origin", execution_path=execution_path)
        # update our local reference to the remote branch so long as it's fast-forwardable or we don't have it yet..)
        hasRemote = git.hasBranch(f"origin/{subPublic}", execution_path=execution_path)
        hasBranch = git.hasBranch(subPublic, execution_path=execution_path)
        if hasRemote and (git.branchUpToDateWith(subPublic, f"origin/{subPublic}", execution_path=execution_path) or not hasBranch):
            git.fetch("origin {subPublic}:{subPublic}", execution_path=execution_path)
        ret = self.mergeIntoCurrent(subPublic, mergeArgs, subproject, execution_path=execution_path)
        # skip nested subprojects that fail to merge
        if not ret and not isSubmodule and not git.conflictedFiles(execution_path=execution_path):
            logging.info(f"Unable to merge subproject {subproject}, skipping...")
            ret = True
        conflict = not ret
        if conflict:
            self.progress["stopPoint"] = "Subproject: {subproject}"
            subprojectKey = "submodules" if isSubmodule else "nested"
            self.progress[subprojectKey] = subprojects
            self.progress["cwd"] = cwd
            conflictedFiles = git.conflictedFiles(execution_path=execution_path)
            if conflictedFiles:
                if isSubmodule:
                    typeStr = "submodule"
                else:
                    typeStr = "nested subproject"

                logging.info(
                    f"Merge in {typeStr} {subproject} from {subPublic} to " +
                    f"{git.currentBranch(execution_path=self.command_path)} issued conflicts. Resolve and " +
                    "commit those changes \nusing git mergetool and git " +
                    "commit in the submodule, then continue using grape\n" +
                    f"{args['<<cmd>>']} --continue")
            else:
                logging.info(
                    f"Merge in {subproject} failed for an unhandled " +
                    "reason. You may need to stash / commit your current\n" +
                    "changes before doing the merge. Inspect git output " +
                    "above to troubleshoot. Continue using\ngrape " +
                    f"{args['<<cmd>>']} --continue.")
            return False
        # if we are resuming from a conflict, the above grape m call would have taken care of continuing.
        # clear out the --continue flag.
        args["--continue"] = False
        # stage the updated submodule
        if isSubmodule:
            git.add(subproject, execution_path=cwd)
        self.progress[f"Subproject: {subproject}"] = "finished"
        return True

    def outerLevelMerge(self, args, branch):
        logging.info(f"Merging changes from {branch}" +
                     " into your current branch...")

        conflict = not self.mergeIntoCurrent(branch, args, "outer level project", execution_path=self.command_path)

        if conflict:
            conflictedFiles = git.conflictedFiles(execution_path=self.command_path)
            if conflictedFiles:
                return conflictedFiles
            else:
                logging.warning("Merge issued error, but no conflicts. Aborting...")
                return False
        else:
            self.progress["outerLevelDone"] = True
            return []

    def merge(self, branch, strategy, args):
        squashArg = "--squash" if args["--squash"] else ""
        try:
            git.merge(f"{squashArg} {branch} {strategy}",
                      execution_path=self.command_path)
            return True
        except grape_errors.GrapeGitError as error:
            logging.error(error.gitOutput)
            if error.has_conflict():
                if args['--at'] or args['--ay']:
                    if args['--at']:
                        logging.info("Resolving conflicted files by " +
                                     f"accepting changes from {branch}.")
                        checkoutArg = "--theirs"
                    else:
                        logging.info("Resolving conflicted files by accepting changes from your branch.")
                        checkoutArg = "--ours"
                    try:
                        path = git.baseDir(execution_path=self.command_path)
                        git.checkout(f"{checkoutArg} {path}",
                                     execution_path=self.command_path)
                        git.add(f"{path}", execution_path=self.command_path)
                        git.commit(f"-m 'Resolve conflicts using {checkoutArg}'",
                                   execution_path=self.command_pat)
                        return True
                    except grape_errors.GrapeGitError as resolveError:
                        logging.error(resolveError.gitOutput)
                        return False
                else:
                    logging.warning(
                        "Conflicts generated. Resolve using git mergetool," +
                        f" then continue with grape {args['<<cmd>>']} " +
                        "--continue. ")
                    return False
            else:
                logging.error(f"Merge command {error.gitCommand} failed." +
                              " Quitting.")
                return False

    def continueLocalMerge(self, args, *, execution_path):
        # "utility.userInput" is a function
        git.fixActiveSubmodules(self.workspace_dir, utility.userInput)
        status = git.status(execution_path=execution_path)
        # Commit after conflict resolution.
        # If there were no conflicts in the outer-level repo, we still need to commit the submodule gitlinks.
        if "All conflicts fixed but you are still merging." in status or \
               (not "You have unmerged paths." in status and \
                "Changes to be committed:" in status):
            git.commit(f"-m \"GRAPE: merge from {args['--public']} after " +
                       "conflict resolution.\"", execution_path=execution_path)
            return True
        else:
            return False

    def mergeIntoCurrent(self, branchName, args, projectName, *, execution_path):
        choice = False
        strategy = 'am' 
        if args["--continue"]:
            if self.continueLocalMerge(args, execution_path=execution_pat):
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
            if args['--askAll']:
                repoSpec = f" in {projectName}"
            else:
                repoSpec = ''
            strategy = utility.userInput(
                f"How do you want to resolve changes{repoSpec}? " +
                "[am / as / at / aT / ay / aY] \nam: Auto Merge (default) \n" +
                "as: Safe Merge - issues conflicts if both branches touch " +
                "same file.\nat: Accept Theirs - accept changes in " +
                f"{branchName} if both branches touch same file" +
                "\naT: Accept Theirs (if conflicted) - resolves conflicts by "+
                f"accepting changes in {branchName}\nay: Accept Yours - "+
                "accept changes in current branch if both branches touch " +
                "same file\naY: Accept Yours (if conflicted) - resolves " +
                "conflicts by using changes in current branch.", "am")

        if strategy == 'am':
            args["--am"] = True
            logging.info("Merging using git's default strategy...")
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
                logging.info("Merging forcing conflicts whenever both branches edited the same file...")
            elif strategy == 'at':
                args["--at"] = True
            elif strategy == 'ay':
                args["--ay"] = True
            base = git.gitDir(execution_path=self.command_path)
            if base == "":
                return False
            attributes = os.path.join(base, ".gitattributes")
            tmpattributes = None
            if os.path.exists(attributes):
                tmpattributes = os.path.join(base, ".gitattributes.tmp")
                # save original attributes file
                shutil.copyfile(attributes, tmpattributes)
                #append merge driver strategy to the attributes file
                with io.open(attributes, 'a') as f:
                    f.write("* merge=verify")
            else:
                with io.open(attributes, 'w') as f:
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
            logging.info("Merging using recursive strategy, resolving " +
                         f"conflicts cleanly with changes in {branchName}...")
            choice = self.merge(branchName, "-Xtheirs", args)
        elif strategy == 'aY':
            args["--aY"] = True
            logging.info("Merging using recursive strategy, resolving conflicts cleanly with current branch's changes...")
            choice = self.merge(branchName, "-Xours", args)

        return choice

    def setDefaultConfig(self, config):
        try:
            config.add_section(self.SECTION_FLOW)
        except configparser.DuplicateSectionError:
            pass
        config.set(self.SECTION_FLOW, "publicBranches", "develop master")
        config.set(self.SECTION_FLOW, "topicPrefixMappings", "?:develop")
        config.set(self.SECTION_FLOW, "topicDestinationMappings", "none")

    def _resume(self, args, *, workspace_dir):
        super(MergeDevelop, self)._resume(args, workspace_dir)
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
