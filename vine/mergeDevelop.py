import configparser
import io
import logging
import os
import re
import time
from vine import checkout
from vine import config_parser_global
from vine import config_parser_user
from vine import Gitlab
from vine import grape_errors
from vine import grapeGit as git
from vine import multi_repo_cmd_launcher
from vine import utility
from vine import version as grapeVersion
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
                    [--recurse | --noRecurse | --nestedSubprojectsOnly]
                    [--forceUpdate | --noUpdate | --ensureCleanUpdate]
                    [--noChecks]
                    [--squash]
                    [--filter=<args>]
           grape-md --traverseTrainRefs --topic=<branch> [--tagProposedVersion]
                    [--user=<GitLabUserName>]
                    [--codeReviewsURL=<httpsURL>]
                    [--verifySSL=<bool>]
                    [--project=<GitLabProjectKey>]
                    [--repo=<GitLabRepoName>]
                    [--ssh_pat_url=<url>]
                    [--ssh_pat_port=<int>]
           grape-md --traverseMergedResult --topic=<branch>


    Options:
        --public=<branch>        Overrides the public branch to merge from.
                                 Default behavior is to merge according to
                                 .grapeconfig.flow.topicPrefixMappings.
        --subpublic=<branch>     Overrides the submodules' public branch to merge from. Default behavior is to merge
                                 according to .grapeconfig.flow.submoduleTopicPrefixMappings.
        --am                     Perform the merge using git's default strategy. (default)
        --as                     Perform the merge issuing conflicts on any file modified by both branches.
        --at                     Perform the merge using the public branch's version for any file modified by both branches.
        --aT                     Perform the merge resolving conficts using the public branch's version.
        --ay                     Perform the merge using the your topic branch's version for any file modified by both branches.
        --aY                     Perform the merge resolving conflicts using your topic branch's version.
        --recurse                Perform merges in submodules first, then merge in the outer level keeping the
                                 results of submodule merges. Nested subprojects are also merged.
        --noRecurse              Do not perform merges in submodules, just attempt to merge the gitlinks.
                                 Nested subprojects are also merged.
        --nestedSubprojectsOnly  Do not perform merges in outer level or submodules, just nested subprojects.
        --continue               Resume the most recent call to grape md that issued conflicts in this workspace.
        --forceUpdate            Force update local versions of the public branch before attempting merges.
        --noUpdate               Do not update local versions of the public branch before attempting merges.
        --ensureCleanUpdate      Return failure if update of local versions fails.
        --noChecks               Skip workspace consistency checks.
        --squash                 Perform squash merges.
        --traverseTrainRefs      Do the necessary merges to merge all branches in the active merge train into this one for all nested subprojects.
        --traverseMergedResult   Do the necessary merges to merge all nested subprojects up to the point of the merged result in the top level.
        --topic=<branch>         Topic branch we are merging into. This is defined explicitly with --traverseTrainRefs/--traverseMergedResult
                                 to define the starting point (this ensures we don't merge something behind the --topic branch).
        --tagProposedVersion     Useful for merge train workflows, this option tags --topic with a proposed version tag based on the number
                                 of train cars that needed to be merged during this call to grape md --traverseTrainRefs.
        --codeReviewsURL=<url>   Your Gitlab URL, e.g. https://your.home.org/gitlab.
                                 [default: .grapeconfig.project.codeReviewsURL]
        --verifySSL=<bool>       Set to False to ignore SSL certificate verification issues.
                                 [default: .grapeconfig.project.verifySSL]
        --project=<project>      Your GitLab Project. See grape-review for more details.
                                 [default: .grapeconfig.project.name]
        --repo=<repo>            Your GitLab repo. See grape-review for more details.
                                 [default: .grapeconfig.repo.name]
        --ssh_pat_url=<url>      SSH URL for generating Personal Access Tokens to authenticate into a Code Review service's
                                 REST API.
                                 [default: .grapeconfig.repo.ssh_pat_url]
        --ssh_pat_port=<int>     Port number to issue ssh command over to generate a Personal Access Token for authentication
                                 into a Code Review service's REST API.
                                 [default: .grapeconfig.repo.ssh_pat_port]
        --filter=<arg>           Optional clone filter argument to use if any subprojects get cloned during the merge.
                                 WARNING! This is still experimental and may have issues with grape workflows.
                                 In particular, tree:0 has performance issues with git rev-list/log command on specified
                                 files (it appears to download each commit separately).


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
        if "--traverseTrainRefs" in args and args["--traverseTrainRefs"]:
            return self.traverseTrainRefs(args, nested)
        if "--traverseMergedResult" in args and args["--traverseMergedResult"]:
            return self.traverseMergedResult(args, nested)

        self.set_progress_file(execution_path=self.workspace_dir)

        if "<<cmd>>" not in args:
            args["<<cmd>>"] = "md"
        branch = args["--public"]
        if not branch:
            branch = config_parser_global.grapeConfig().getPublicBranchFor(git.currentBranch(execution_path=self.workspace_dir))
            if not branch:
                logging.error("ERROR: public branches must be configured for grape md to work.")
        args["--public"] = branch

        if "--nestedSubprojectsOnly" in args and args["--nestedSubprojectsOnly"]:
            logging.info(f"Calling grape up --public={branch} --noTopLevel --noRecurse --recurseSubprojects to ensure local reference to branch exists.")
            menu = grapeMenu.menu(workspace_dir=self.workspace_dir)
            menu.applyMenuChoice('up', ['up', f'--public={branch}','--noTopLevel','--noRecurse','--recurseSubprojects'])
            self.performSubprojectMerges(args, branch, nested, False, [], ignoreInProgress=True)
            return True

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
            upCmd = ['up', f'--public={args["--public"]}']
            if not args["--forceUpdate"]:
                upCmd.append("--noForce")
            ret = menu.applyMenuChoice('up', upCmd)
            if args["--ensureCleanUpdate"] and ret is False:
                logging.error("Failed to update public branches! Please address above issues (or run with --noUpdate) and try again.")
                return False
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

        if not self.performSubprojectMerges(args, branch, nested, recurse, submodules):
            return False
        
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
                uvArgs = ["--allSubmodules", "--skipNestedSubprojects"]
                if args["--filter"]:
                    uvArgs.append("--filter="+args["--filter"])
                menu.applyMenuChoice("uv", uvArgs)
                menu.set_workspace_dir(original_workspace_dir)

        # clear out the progress now that we're done so that when we are called a second time during a publish
        # we don't just skip the md
        self.progress = {}
        return True

    def lookupActiveMergeTrainBranches_new_version(self, args, repo):
       current_branch = args['--topic']
       config = config_parser_global.grapeConfig()
       target_branch = config.getPublicBranchFor(current_branch)
       # Now that we know the target branch, get the SHAs of all the merges between target branch and HEAD, including the SHAs of the parents.
       log_descriptions = git.log(f"origin/{target_branch}..HEAD --oneline --parents --merges --no-abbrev-commit", execution_path=self.workspace_dir).splitlines()
       # Reverse the list so that the target branch is first and newer commits are later.
       log_descriptions.reverse()
       # Save the SHA of the target branch
       target_SHA = git.SHA(f"origin/{target_branch}", execution_path=self.workspace_dir)

       start_time = time.time()
       # We may need to handle prior cars that have already been merged, so we get all merge train cars and start from the end (latest).
       # The Python GitLab API doesn't directly support merge train lookups by target branch, but we can hack it by specifying the path.
       # TODO If this query gets too large such that it affects performance, we may need to paginate the lookup.
       mergeTrainCars = repo.project.merge_trains.list(all=True, path=f'/projects/{repo.project.id}/merge_trains/{target_branch}', sort='desc')
       end_time = time.time()
       logging.info(f"NEW: Merge train lookup took {end_time-start_time} seconds")

       versionTag_SHA = None

       for car in mergeTrainCars:
           mr_iid = car.merge_request['iid']
           mr = repo.pullRequests(state="all", id=mr_iid)[0]
           branch = mr.fromRef()
           status = car.status
           order = -1
           if branch == current_branch:
             # Get the SHA of the most recent version tag
             config = config_parser_global.grapeConfig()
             prefix = config.get(self.SECTION_VERSIONING, "prefix")
             versionTag = git.describe(f"--abbrev=0 --match '{prefix}*'", execution_path=self.workspace_dir)
             versionTag_SHA = git.gitcmd(f"rev-list -n 1 {versionTag}", "rev-list failed", execution_path=self.workspace_dir)
             logging.info(f"NEW: Found current branch, targeting {target_branch} at {target_SHA}.")
             logging.info(f"NEW: Latest version: {versionTag} at {versionTag_SHA}.")
             logging.info(f"NEW: Log since {target_branch}\n{log_descriptions}.")
             continue

           if mr.toRef() != target_branch:
             # Skip merge request if it doesn't target the same branch.
             # This should not happen since we looked up the merge train by target branch.
             logging.info(f"NEW: WARNING MR {mr_iid} targets {mr.ToRef()} instead of {target_branch}, skipping...")
             continue

           if status == 'merged':
             # The car may be already been merged but not yet accounted for in this car, so we need to check for that.
             merge_sha = mr.mergerequest.merge_commit_sha
             # If the merge request corresponds to latest tagged version, we don't need to look at this car
             if merge_sha == versionTag_SHA:
                # TODO can we ignore merge cars (earlier) after this one?
                logging.info(f"NEW: {status} MR {mr_iid} matches {versionTag}, skipping...")
                continue
             # If the merge request corresponds to the current target branch, we still may need to consider it,
             # as the subprojects may not have been merged yet (and the version number may not have been tagged).
             if merge_sha == target_SHA:
                # TODO can we ignore merge cars (earlier) after this one?
                logging.info(f"NEW: {status} MR {mr_iid} matches {target_branch}...")
                order = 0
             else:
                 # Only include a merged branch if the merge associated with its MR is between the target branch and HEAD
                 found_merge = False
                 for line in log_descriptions:
                    order = order + 1
                    if merge_sha in line:
                       found_merge = True
                       logging.info(f"NEW: {status} merge commit {merge_sha} for MR {mr_iid} found...")
                       break
                 # If the merge commit sha is not found, try using the sha from the merge request (matching with merge commit parents)
                 if not found_merge:
                    merge_sha = mr.mergerequest.sha
                    for line in log_descriptions:
                       order = order + 1
                       if merge_sha in line:
                          found_merge = True
                          logging.info(f"NEW: {status} {merge_sha} for MR {mr_iid} found...")
                          break
                 if not found_merge:
                    logging.info(f"NEW: {status} {merge_sha} for MR {mr_iid} not found, skipping...")
                    continue
           else:
             # The car is still running, need to determine if it's in the history of our car or not.
             # Use the sha from the merge request and see if it matches a merge commit parent.
             merge_sha = mr.mergerequest.sha
             found_merge = False

             for line in log_descriptions:
               order = order + 1
               if merge_sha in line:
                  found_merge = True
                  logging.info(f"NEW: {status} {merge_sha} for MR {mr_iid} found...")
                  break
             # Only include a merged branch if the merge associated with its MR is between the target branch and HEAD
             if not found_merge:
               logging.info(f"NEW: {status} {merge_sha} for MR {mr_iid} not found, skipping...")
               continue

           logging.info(f"NEW: Found branch: {branch} at position {order} ({merged}).")
           branches[order] = branch

       # Put the target branch first in the merge train, dropping out any None entries leftover
       branches = [target_branch] + [b for b in branches if b]
       return branches

    def lookupActiveMergeTrainBranches(self, args):
       if "gitlab" not in args["--codeReviewsURL"]:
           logging.info("merge train should only be used with GitLab.")
           return False

       name = args["--user"]
       if not name:
           name = utility.getUserName()
       verify = True if args["--verifySSL"].lower() == "true" else False

       grape_gitlab = Gitlab.GrapeGitlabAdapter(name, url=args["--codeReviewsURL"],
                                                verify=verify,
                                                port=int(args["--ssh_pat_port"]),
                                                ssh_path = args["--ssh_pat_url"],
                                                workspace_dir=self.workspace_dir
                                               )
       repo = grape_gitlab.project(args["--project"]).repo(args["--repo"])
       try:
           test_branches = self.lookupActiveMergeTrainBranches_new_version(args, repo)
       except Exception as e:
           logging.info(f"lookupActiveMergeTrainBranches_new_version threw exception {e}")
           test_branches = []

       branches = []
       current_branch = args['--topic']
       start_time = time.time()
       # We may need to handle prior cars that have already been merged, so we get all merge train cars and start from the end (latest).
       # If the Python GitLab API supported merge train lookups by target branch, the scope of this lookup could be reduced.
       # TODO If this query gets too large such that it affects performance, we may need to paginate the lookup.
       mergeTrainCars = repo.project.merge_trains.list(all=True, sort='desc')
       end_time = time.time()
       logging.info(f"Merge train lookup took {end_time-start_time} seconds")

       target_branch = None
       log_descriptions = None
       target_SHA = None
       versionTag_SHA = None
       for car in mergeTrainCars:
           # Use the merge request to look up the branch
           mr_iid = car.merge_request['iid']
           mr = repo.pullRequests(state="all", id=mr_iid)[0]
           branch = mr.fromRef()
           if branch == current_branch:
              # For the current branch, just register the target branch
              target_branch = mr.toRef()
              # Now that we know the target branch, get the SHAs of all the merges between target branch and HEAD.
              log_descriptions = git.log(f"origin/{target_branch}..HEAD --oneline --merges --no-abbrev-commit",
                                         execution_path=self.workspace_dir).splitlines()
              # Save the SHA of the target branch
              target_SHA = git.SHA(f"origin/{target_branch}", execution_path=self.workspace_dir)
              # Get the SHA of the most recent version tag
              config = config_parser_global.grapeConfig()
              prefix = config.get(self.SECTION_VERSIONING, "prefix")
              versionTag = git.describe(f"--abbrev=0 --match '{prefix}*'", execution_path=self.workspace_dir)
              versionTag_SHA = git.gitcmd(f"rev-list -n 1 {versionTag}", "rev-list failed", execution_path=self.workspace_dir)
              logging.info(f"Found current branch, targeting {target_branch} at {target_SHA}.")
              logging.info(f"Latest version: {versionTag} at {versionTag_SHA}.")
              logging.info(f"Log since {target_branch}\n{log_descriptions}.")
              continue
           elif not target_branch:
              # Don't start considering other branches until we have found the current one
              continue

           if mr.toRef() != target_branch:
              # Skip merge request if it doesn't target the same branch
              continue

           if car.status == 'merged':
              # The car may be already been merged but not yet accounted for in this car, so we need to check for that.
              merge_sha = mr.mergerequest.merge_commit_sha
              # If the merge request corresponds to latest tagged version, we don't need to look at this or earlier cars.
              if merge_sha == versionTag_SHA:
                 logging.info(f"{car.status} MR {mr_iid} matches {versionTag}, skipping...")
                 break
              # If the merge request corresponds to the current target branch, we still may need to consider it,
              # as the nested subprojects may not have been merged yet.
              if merge_sha == target_SHA:
                 logging.info(f"{car.status} MR {mr_iid} matches {target_branch}...")
              else:
                  found_merge = False
                  for line in log_descriptions:
                     if merge_sha in line:
                        found_merge = True
                        logging.info(f"{car.status} {merge_sha} for MR {mr_iid} found...")
                        break
                  # Only include a merged branch if the merge associated with its MR is between the target branch and HEAD
                  if not found_merge:
                     logging.info(f"{car.status} {merge_sha} for MR {mr_iid} not found, skipping...")
                     continue

           # Prepend the branch, since we are looping over the cars backwards
           logging.info(f"Found branch: {branch} ({car.status}).")
           branches = [branch] + branches

       if not target_branch:
           logging.info(f"{current_branch} not found in merge train!")
           return False
       else:
           # Put the target branch first in the merge train
           branches = [target_branch] + branches

       logging.info(f"NEW VERSION BRANCHES {test_branches}, OLD VERSION BRANCHES {branches}")
       return branches

    def numberOfMergesSinceMostRecentTag(self, args, branch):
        numMerges = 0

        config = config_parser_global.grapeConfig()
        prefix = config.get(self.SECTION_VERSIONING, "prefix")

        # TODO should these have suffix?
        description = grapeVersion.describeLastVersion("", branch=branch, tagPrefix=prefix, execution_path=self.workspace_dir)
        while '-' in description:
            numMerges = numMerges+1
            logging.info(f"branch {branch} is {description}, ticked numMerges to {numMerges}")
            branch = git.parentsOfMergeCommit(branch, execution_path=self.workspace_dir)[0]
            description = grapeVersion.describeLastVersion("", branch=branch, tagPrefix=prefix, execution_path=self.workspace_dir)
            logging.info(f"branch {branch} is {description}")
        return numMerges


    def traverseTrainRefs(self, args, nested):
        from vine import grapeMenu
        branches = self.lookupActiveMergeTrainBranches(args)
        if not branches:
            return False
        logging.info(f"Merge Train Branches: {branches}")
        menu = grapeMenu.menu(workspace_dir=self.workspace_dir)
        # The first branch is always the target branch
        targetBranch = branches[0]
        unmergedTrainBranches = []
        for branch in branches:
            logging.info(f"Calling grape up --public={branch} --noTopLevel --noRecurse --recurseSubprojects to ensure local reference to branch exists.")
            menu.applyMenuChoice('up', ['up', f'--public={branch}','--noTopLevel','--noRecurse','--recurseSubprojects'])
            if not self.performSubprojectMerges(args, branch, nested, False, [], ignoreInProgress=True):
               # Fail if conflict detected
               logging.info("Failed subproject merge!")
               return False
            if branch == targetBranch:
               # Always include the target branch
               unmergedTrainBranches.append(branch)
            else:
               # Only include other branches in the merge train if they are not contained by the target branch
               containingBranches = git.branch(f"-r --contains origin/{branch}", execution_path=self.workspace_dir).split()
               if f"origin/{targetBranch}" not in containingBranches:
                  unmergedTrainBranches.append(branch)
        if args["--tagProposedVersion"]:
            numMerges = self.numberOfMergesSinceMostRecentTag(args,f"origin/{targetBranch}")
            logging.info(f"numMerges = {numMerges}")
            versionargs =  ["tick", "--tag", "-f", "--pushTag",
                            f"--public=origin/{targetBranch}",
                            f"--tagBase=origin/{targetBranch}",
                            f"--numTicks={len(unmergedTrainBranches)+numMerges}",
                            f"--target=origin/{args['--topic']}","--newTagPrefix=proposed_v"]
            logging.info(f"calling grape version {' '.join(versionargs)}")
            menu.applyMenuChoice("version",versionargs)
        return True
            

    def traverseMergedResult(self, args, nested):
        # Make sure we have all tags
        git.fetch("origin '+refs/tags/*:refs/tags/*'", execution_path=self.workspace_dir)
        config = config_parser_global.grapeConfig()
        prefix = config.get(self.SECTION_VERSIONING, "prefix")
        # Get the version of the branch
        # TODO should these have suffix?
        versionTag = grapeVersion.describeLastVersion("--abbrev=0", branch=f"origin/{args['--topic']}", tagPrefix=prefix, execution_path=self.workspace_dir)
        # Get the version of the merged result
        mergedVersionTag = grapeVersion.describeLastVersion("--abbrev=0", branch="", tagPrefix=prefix, execution_path=self.workspace_dir)
        if versionTag == mergedVersionTag:
            logging.info(f"No versions to merge, already at {versionTag}.")
            return True
        # Get all the version tags after the tagged version, oldest first
        branch_log = git.log(f"--oneline --decorate --reverse --no-color HEAD --not {versionTag}", execution_path=self.workspace_dir)
        tagsFetched = False
        for line in branch_log.splitlines():
           match = re.search(f"tag: ({prefix}[^),]+)", line)
           if match:
              if not tagsFetched:
                 logging.info(f"Calling grape up --noTopLevel --noRecurse --recurseSubprojects to ensure tags are fetched.")
                 from vine import grapeMenu
                 menu = grapeMenu.menu(workspace_dir=self.workspace_dir)
                 menu.applyMenuChoice('up', ['up','--noTopLevel','--noRecurse','--recurseSubprojects'])
                 tagsFetched = True
              # Attempt to merge each version (this will be a no-op if the tag is not found)
              version = match.group(1)
              if not self.performSubprojectMerges(args, version, nested, False, [], ignoreInProgress=True):
                  # Fail if conflict detected
                  logging.info("Failed subproject merge!")
                  return False
        return True


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
                config = config_parser_global.grapeConfig()
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
                if "Unable to merge subproject" in info:
                   self.progress[f"Subproject: {repo}"] = "finished"
                else:
                   all_good = False
        if not all_good:
            if not ignoreInProgress:
               self.progress["stopPoint"] = "subproject merge"
               self.dumpProgress(args)
            return False
        return True


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
                    if "<<cmd>>" in args:
                       logging.warning(
                           "Conflicts generated. Resolve using git mergetool," +
                           f" then continue with grape {args['<<cmd>>']} " +
                           "--continue. ")
                    else:
                       logging.warning("Conflicts generated.")
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
        return f"Unable to merge subproject {repo}, skipping..."
    conflict = not ret
    if conflict:
        subprojectKey = "submodules" if isSubmodule else "nested"
        conflictedFiles = git.conflictedFiles(execution_path=repo)
        if conflictedFiles:
            if isSubmodule:
                typeStr = "submodule"
            else:
                typeStr = "nested subproject"

            if "<<cmd>>" in args:
               info = f"Merge in {typeStr} {repo} from {subPublic} to " \
                      f"{git.currentBranch(execution_path=repo)} issued conflicts. Resolve and " \
                      "commit those changes \nusing git mergetool and git " \
                      f"commit in the {typeStr}, then continue using grape\n" \
                      f"{mergeArgs['<<cmd>>']} --continue"
            else:
               info = f"Merge in {typeStr} {repo} from {subPublic} to " \
                      f"{git.currentBranch(execution_path=repo)} issued conflicts"
        else:
            if "<<cmd>>" in args:
               info = f"Merge in {repo} failed for an unhandled " \
                      "reason. You may need to stash / commit your current\n" \
                      "changes before doing the merge. Inspect git output " \
                      "above to troubleshoot. Continue using\ngrape " \
                      f"{mergeArgs['<<cmd>>']} --continue."
            else:
               info = f"Merge in {repo} failed for an unhandled reason"
        return info
    return True
