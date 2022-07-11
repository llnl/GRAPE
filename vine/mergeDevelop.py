import configparser
import io
import logging
import os
from vine import checkout
from vine import config_parser_global
from vine import config_parser_user
from vine import grape_errors
from vine import grapeGit as git
from vine import multi_repo_cmd_launcher
from vine import utility
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.option import Option
from vine.resumable import Resumable
from vine.vine_logging import log_wrapper


# pull and merge in an up-to-date development branch
class MergeDevelop(Resumable, Option, WorkspaceDirHandler):
    """
    grape md  (Merge Down)
    merge changes from a public branch into your current topic branch
    If executed on a public branch, performs a pull --rebase to update your local public branch.
    Usage: grape-md [--public=<branch>] [--subpublic=<branch>]
                    [--am | --as | --at | --aT | --ay | --aY ]
                    [--continue]
                    [--recurse | --noRecurse]
                    [--noUpdate]
                    [--noChecks]
                    [--squash]
                    [--traverseTrainRefs --topic=<branch>]


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
        --recurse               Perform merges in submodules first, then merge in the outer level keeping the
                                results of submodule merges.
        --noRecurse             Do not perform merges in submodules, just attempt to merge the gitlinks.
        --continue              Resume the most recent call to grape md that issued conflicts in this workspace.
        --noUpdate              Do not update local versions of the public branch before attempting merges.
        --noChecks              Skip workspace consistency checks.
        --squash                Perform squash merges.
        --traverseTrainRefs     Do the necessary merges to merge all branches in the active merge train into this one for all nested subprojects.
        --topic=<branch>        Topic branch we are merging into (defined explicitly with --traverseTrainRefs to ensure we don't merge something
                                behind the --topic branch on the train)




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
            currentBranch = git.currentBranch(execution_path=self.workspace_dir)
        except grape_errors.GrapeGitError:
            currentBranch = 'unknown'
        publicBranch = self.lookupPublicBranch(execution_path=self.workspace_dir)

        return f"Merge latest changes on {publicBranch} into {currentBranch}"

    @log_wrapper
    def execute(self, args):
        # Imported here to avoid circular dependencies
        from vine import grapeMenu
        nested = getattr(self.progress, 'nested', config_parser_user.getAllActiveNestedSubprojectPrefixes(workspaceDir=self.workspace_dir))
        if "--traverseTrainRefs" in args:
            self.traverseTrainRefs(args, nested)
            return True

        self.set_progress_file(execution_path=self.workspace_dir)

        if "<<cmd>>" not in args:
            args["<<cmd>>"] = "md"
        branch = args["--public"]
        if not branch:
            branch = config_parser_global.grapeConfig().getPublicBranchFor(git.currentBranch(execution_path=self.workspace_dir))
            if not branch:
                logging.error("ERROR: public branches must be configured for grape md to work.")
        args["--public"] = branch

        # check to see if we already have the branch
        try:
            git.shortSHA(branch, execution_path=self.workspace_dir)
        except:
            # stripping of origin/ from the branch specification
            if branch.startswith("origin/"):
                basebranch = branch[len("origin/"):]
            else:
                basebranch = branch
            # see if the branch exists locally
            try:
                git.shortSHA(basebranch, execution_path=self.workspace_dir)
            except:
                # otherwise fetch it
                git.fetch("origin", f"{basebranch}:{basebranch}",
                          execution_path=self.workspace_dir)

        # determine whether to merge in subprojects that have changed
        if "submodules" in self.progress:
            submodules = self.progress["submodules"]
        else:
            modifiedSubmodules = git.getModifiedSubmodules(self.workspace_dir, branch, git.currentBranch(execution_path=self.workspace_dir))
            activeSubmodules = git.getActiveSubmodules(execution_path=self.workspace_dir)
            submodules = [sub for sub in modifiedSubmodules if sub in activeSubmodules]


        config = config_parser_global.grapeConfig()
        recurse = config.getboolean(Option.SECTION_WORKSPACE, "manageSubmodules") or args["--recurse"]
        recurse = recurse and (not args["--noRecurse"]) and len(submodules) > 0
        args["--recurse"] = recurse

        if "conflictedFiles" in self.progress:
            conflictedFiles = self.progress["conflictedFiles"]
        else:
            conflictedFiles = []

        # take note of whether all submodules are currently present, assume user wants to add any new submodules to WS if so
        activeSubmodulesCheck0 = git.getActiveSubmodules(execution_path=self.workspace_dir)

        self.progress["allActive"] = set(git.getAllSubmodules(execution_path=self.workspace_dir)) == set(git.getActiveSubmodules(execution_path=self.workspace_dir))

        # checking for a consistent workspace before doing a merge
        menu = grapeMenu.menu(workspace_dir=self.workspace_dir)
        if not args["--noChecks"]:
            logging.info("Checking for a consistent workspace before performing merge...")
            ret = menu.applyMenuChoice("status", ['--failIfInconsistent'])
            if ret is False:
                logging.error("Workspace inconsistent! Aborting attempt to do the merge. Please address above issues and then try again.")
                return False

        if "updateLocalDone" not in self.progress and not args["--noUpdate"]:
            # make sure public branches are to date in outer level repo.
            logging.info("Calling grape up to ensure topic and public branches are up-to-date. ")
            menu.applyMenuChoice('up', ['up', f'--public={args["--public"]}'])
            self.progress["updateLocalDone"] = True

        # "utility.userInput" is a function
        git.fixActiveSubmodules(self.workspace_dir, utility.userInput)

        addedModules = []
        removedModules = []
        changedURLModules = []
        if recurse:
            checkout.parseGitModulesDiffOutput(
                git.currentBranch(execution_path=self.workspace_dir), branch, addedModules,
                removedModules, changedURLModules,
                workspace_dir=self.workspace_dir)
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
            currentBranch = git.currentBranch(execution_path=self.workspace_dir)
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

        self.performSubprojectMerges(args, branch, nested, recurse, submodules)
        
        cleanAfterMerge = continueLocalMerge(args, execution_path=self.workspace_dir)
        if not cleanAfterMerge:
            conflictedFiles = git.conflictedFiles(execution_path=self.workspace_dir)
            if len(conflictedFiles) != 0:
                self.progress["stopPoint"] = "resolve conflicts"
                self.dumpProgress(args, "GRAPE: Outer level merge generated conflicts. Please resolve using git mergetool " +
                                        f"and then \n continue by calling 'grape {args['<<cmd>>']} --continue' .")
                return False

        original_workspace_dir = menu.workspace_dir
        menu.applyMenuChoice("runHook", ["post-merge", '0', "--noExit"])
        menu.set_workspace_dir(original_workspace_dir)

        # ensure all submodules are currently present in WS if all submodules were present at the beginning of merge
        if self.progress["allActive"]:
            activeSubmodulesCheck1 = git.getActiveSubmodules(execution_path=self.workspace_dir)
            if (set(activeSubmodulesCheck0) != set(activeSubmodulesCheck1)):
                logging.info("Updating new submodules using grape uv --allSubmodules")
                original_workspace_dir = menu.workspace_dir
                menu.applyMenuChoice("uv", ["--allSubmodules", "--skipNestedSubprojects"])
                menu.set_workspace_dir(original_workspace_dir)

        # clear out the progress now that we're done so that when we are called a second time during a publish
        # we don't just skip the md
        self.progress = {}
        return True


    def lookupActiveMergeTrainBranches(self, args):
       trainRefsLines = git.lsRemote("origin --refs 'refs/merge-requests/*/train'")

       if trainRefsLines:
          trainRefsLines = trainRefsLines.split('\n')
       print(trainRefsLines)
       current_branch_train_ref = None
       public_branch = None
       next_car = {}
       car_branches = {}

       for line in trainRefsLines:
           print(line)
           sha,ref = line.split()
           print(f"SHA <{sha}> REF <{ref}>")
           # fetch remote refs/merge-requests/<merge_request_id>/train to local merge-requests/<merge_request_id>/train
           local_branch = ref.split('/')[1]
           git.fetch(f"origin {ref}:{local_branch}")
           # lookup the commit message for the train merge commit
           commit_msg = git.commitDescriptionShort(local_branch, execution_path=self.workspace_dir).strip().split("Merge branch ")[1]
           # parse the commit message into branch, next_train_car, current_train_car
           commit_msg = commit_msg.split(" with ")
           branch = commit_msg[0]
           commit_msg = commit_msg[1].split(" into ")
           next_train_car = commit_msg[0].split("refs/")[1]
           current_train_car = commit_msg[1].split("refs/")[1]
           if args["--topic"] == branch:
               current_branch_train_ref = current_train_car
           next_car[current_train_car] = next_train_car
           car_branches[current_train_car] = branch
           # store the public branch wehen we see it
           next_train_car_toks = next_train_car.split('/')
           if next_train_car_toks[0] == "heads":
               public_branch = next_train_car_toks[1]
       train_ref = current_branch_train_ref
       branches = []
       #starting from the current train car, identify branches for all train cars leading to the public branch merge
       while next_car[current_branch_train_ref] != f"heads/{public_branch}":
           branches = [car_branches[next_car[current_branch_train_ref]]] + branches
           current_branch_train_ref = next_car[current_branch_train_ref]
       branches = [f"{public_branch}"] + branches
       return branches


    def traverseTrainRefs(self, args, nested):
        branches = self.lookupActiveMergeTrainBranches(args)
        for branch in branches:
            self.performSubprojectMerges(args, branch, nested, False, [], ignoreInProgress=True)


    def performSubprojectMerges(self, args, branch, nested, recurse, submodules, ignoreInProgress=False):
        listOfRepoBranchArgTuples = [] 
        # queue merges for nested subprojects
        for subproject in nested:
            # if we did this merge in a previous run, don't do it again
            key = f"Subproject: {subproject}"
            if not ignoreInProgress and key in self.progress and self.progress[key] == "finished":
               logging.info(f"merge in {subproject} already completed")
               continue 
            listOfRepoBranchArgTuples.append((subproject,branch,[args,False]))
        
        # queue merges for submodules
        if recurse and len(submodules) > 0:
            if args["--subpublic"]:
                # respect the callers wishes (usually this is grape m , mr, or pull)
                subPublic = args["--subpublic"]
            else:
                # default is to merge the submodule branch that is mapped to the public branch
                subBranchMappings = config.getMapping(Option.SECTION_WORKSPACE, "submodulePublicMappings")
                subPublic = subBranchMappings[config.getPublicBranchFor(branch)]
            for submodule in submodules:
                # if we did this merge in a previous run, don't do it again
                key = f"Subproject: {submodule}"
                if key in self.progress and self.progress[key] == "finished":
                   logging.info(f"merge in {submodule} already completed")
                   continue 
                listOfRepoBranchArgTuples.append((submodule, subPublic, [args,  True]))

        repos = [x[0] for x in listOfRepoBranchArgTuples]
        if len(repos) > 0:
            logging.info(f"Launching merges for {', '.join(repos)}")

        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(mergeSubproject,
                                            listOfRepoBranchArgTuples=listOfRepoBranchArgTuples,
                                            workspace_dir=self.workspace_dir)
        
        info_or_true = launcher.launchFromWorkspaceDir(noPause=True, handleMRE=handleMergeSubprojectMRE)
        isSubmodule = [x[2][1] for x in listOfRepoBranchArgTuples]
        all_good = True
        for info, repo, isSubmodule in zip(info_or_true, repos, isSubmodule):
            if info is True:
                # stage the updated submodule
                if isSubmodule:
                    git.add(repo, execution_path=self.workspace_dir)
                logging.info(f"{repo} merged successfully")
                self.progress[f"Subproject: {repo}"] = "finished"
            else:
                logging.info(info)
                all_good = False
        if not all_good:
            self.progress["stopPoint"] = "subproject merge"
            self.dumpProgress(args)
            return False


    def outerLevelMerge(self, args, branch):
        if "outerLevelDone" not in self.progress:
            self.progress["outerLevelDone"] = False
        if self.progress["outerLevelDone"]:
            logging.info(f"Skipping previously performed outer level merge.")
            return []
        logging.info(f"Merging changes from {branch}" +
                     " into your current branch...")

        conflict = not mergeIntoCurrent(branch, args, "outer level project", False, execution_path=self.workspace_dir)

        if conflict:
            conflictedFiles = git.conflictedFiles(execution_path=self.workspace_dir)
            if conflictedFiles:
                return conflictedFiles
            else:
                logging.warning("Merge issued error, but no conflicts. Aborting...")
                return False
        else:
            self.progress["outerLevelDone"] = True
            return []


    def setDefaultConfig(self, config):
        try:
            config.add_section(self.SECTION_FLOW)
        except configparser.DuplicateSectionError:
            pass
        config.set(self.SECTION_FLOW, "publicBranches", "develop master")
        config.set(self.SECTION_FLOW, "topicPrefixMappings", "?:develop")
        config.set(self.SECTION_FLOW, "topicDestinationMappings", "none")

    def _resume(self, args, *, workspace_dir):
        super(MergeDevelop, self)._resume(args, workspace_dir=workspace_dir)
        if self.progress["stopPoint"] == "public rebase":
            # recover from conflicts by continuing the rebase
            git.rebase("--continue", execution_path=workspace_dir)
            retval = True
        else:
            retval = self.execute(args)
        return retval

    def _saveProgress(self, args):
        super(MergeDevelop, self)._saveProgress(args)
        # this lets grape m know that the --continue is for grape md to resume...
        self.progress["inMD"] = True

def merge(branch, strategy, args, warnOnConflict=True, *, execution_path):
    squashArg = "--squash" if args["--squash"] else ""
    try:
        git.merge(f"{squashArg} {branch} {strategy}",
                  execution_path=execution_path)
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
                    path = git.baseDir(execution_path=execution_path)
                    git.checkout(f"{checkoutArg} {path}",
                                 execution_path=workspace_dir)
                    git.add(f"{path}", execution_path=execution_path)
                    git.commit(f"-m 'Resolve conflicts using {checkoutArg}'",
                               execution_path=execution_path)
                    return True
                except grape_errors.GrapeGitError as resolveError:
                    logging.error(resolveError.gitOutput)
                    return False
            else:
                if warnOnConflict:
                    logging.warning(
                        "Conflicts generated. Resolve using git mergetool," +
                        f" then continue with grape {args['<<cmd>>']} " +
                        "--continue. ")
                return False
        else:
            logging.error(f"Merge command {error.gitCommand} failed." +
                          " Quitting.")
            return False

@log_wrapper
def continueLocalMerge(args, *, execution_path):
    status = git.status(execution_path=execution_path)
    logging.debug(f"continueLocalMerge status is {status}")
    # Commit after conflict resolution.
    # If there were no conflicts in the outer-level repo, we still need to commit the submodule gitlinks.
    if "All conflicts fixed but you are still merging." in status or \
           (not "You have unmerged paths." in status and \
            "Changes to be committed:" in status):
        git.commit(f"-m \"GRAPE: merge from {args['--public']} after " +
                   "conflict resolution.\"", execution_path=execution_path)
        return True
    return False

@log_wrapper
def mergeIntoCurrent(branchName, args, projectName, warnOnConflict=True, *, execution_path):
    choice = False
    strategy = 'am'
    if args["--continue"]:
        if continueLocalMerge(args, execution_path=execution_path):
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

    if strategy == 'am':
        args["--am"] = True
        logging.info("Merging using git's default strategy...")
        choice = merge(branchName, "", args, warnOnConflict, execution_path=execution_path)
    elif strategy in ['as', 'at', 'ay']:
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
        base = git.gitDir(execution_path=execution_path)
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
        choice = merge(branchName, "", args, warnOnConflict, execution_path=execution_path)

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
        choice = merge(branchName, "-Xtheirs", args, warnOnConflict, execution_path=execution_path)
    elif strategy == 'aY':
        args["--aY"] = True
        logging.info("Merging using recursive strategy, resolving conflicts cleanly with current branch's changes...")
        choice = merge(branchName, "-Xours", args, warnOnConflict, execution_path=execution_path)

    return choice

@log_wrapper
def handleMergeSubprojectMRE(mre):
    for e, repo, branch in zip(mre.exceptions(), mre.repos(), mre.branches()):
        try:
            raise e
        except grape_errors.GrapeGitError as e2:
            logging.error(f" mergeSubproject  of {branch} {repo}")
            logging.error(f"{e2.gitOutput}")

def mergeSubproject(branch, repo, args, *, workspace_dir):
    subPublic = branch 
    mergeArgs = args[0].copy()
    isSubmodule= args[1]
    mergeArgs["--public"] = subPublic

    submodule_or_subproject = "submodule" if isSubmodule else "subproject"
    logging.info(f"Merging {subPublic} into {git.currentBranch(execution_path=repo)} " +
                 f"for {submodule_or_subproject} {repo}")
    git.fetch("origin", execution_path=repo)
    # update our local reference to the remote branch so long as it's fast-forwardable or we don't have it yet..)
    hasRemote = git.hasBranch(f"origin/{subPublic}", execution_path=repo)
    hasBranch = git.hasBranch(subPublic, execution_path=repo)
    if hasRemote and (git.branchUpToDateWith(subPublic, f"origin/{subPublic}", execution_path=repo) or not hasBranch):
        git.fetch("origin {subPublic}:{subPublic}", execution_path=repo)
    ret = mergeIntoCurrent(subPublic, mergeArgs, repo, True, execution_path=repo)
    # skip nested subprojects that fail to merge
    info = ''
    if not ret and not isSubmodule and not git.conflictedFiles(execution_path=repo):
        info = f"Unable to merge subproject {repo}, skipping..."
        ret = True
    conflict = not ret
    if conflict:
        subprojectKey = "submodules" if isSubmodule else "nested"
        conflictedFiles = git.conflictedFiles(execution_path=repo)
        if conflictedFiles:
            if isSubmodule:
                typeStr = "submodule"
            else:
                typeStr = "nested subproject"

            info = f"Merge in {typeStr} {repo} from {subPublic} to " \
                   f"{git.currentBranch(execution_path=repo)} issued conflicts. Resolve and " \
                   "commit those changes \nusing git mergetool and git " \
                   f"commit in the {typeStr}, then continue using grape\n" \
                   f"{mergeArgs['<<cmd>>']} --continue"
        else:
            info = f"Merge in {repo} failed for an unhandled " \
                   "reason. You may need to stash / commit your current\n" \
                   "changes before doing the merge. Inspect git output " \
                   "above to troubleshoot. Continue using\ngrape " \
                   f"{mergeArgs['<<cmd>>']} --continue."
        return info
    return True
