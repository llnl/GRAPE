import logging
import os
import re
import shlex
import shutil
import stat
import time
from collections import defaultdict
from vine import config_parser_base
from vine import config_parser_global
from vine import config_parser_user
from vine import config_parser_workspace
from vine import grape_errors
from vine import grapeGit as git
from vine import multi_repo_cmd_launcher
from vine.addSubproject import AddSubproject
from vine.updateView import UpdateView
from vine.option import Option
from vine import submodules as submodule_parser
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine import utility
from vine.vine_logging import log_wrapper


def handledCheckout(repo='', branch='master', args=[], *, workspace_dir):
    # 'workspace_dir' included for continuity with multi_repo_cmd_launcher.
    checkoutargs = args["checkout"]
    sync = args["sync"]
    quiet = args["quiet"]
    verbose = args["verbose"]
    if sync:
        # attempt to fetch the requested branch
        try:
            git.fetch("origin", f"{branch}:{branch}", execution_path=repo)
        except grape_errors.GrapeGitIndexLockError as e:
            logging.warning(
                f"Skipping sync fetch for {branch} in {repo} because git "
                f"reported an index.lock at {e.indexLockPath}.")
        except:
            # the branch may not exist, but ignore the exception
            # and allow the checkout to throw the exception.
            pass
    try:
        if verbose:
            logging.info(f"checking out {branch} in {repo}")
        git.checkout(f"{checkoutargs} {branch}", execution_path=repo)
    except grape_errors.GrapeGitIndexLockError as e:
        if not quiet:
            logging.info(
                f"waiting for 3 seconds in {branch} in {repo} due to "
                f"index.lock detection at {e.indexLockPath}")
        time.sleep(3)
        if not quiet:
            logging.info(f"retrying checkout out of {branch} in {repo}")
        git.checkout(f"{checkoutargs} {branch}", execution_path=repo)
    except grape_errors.GrapeGitError as e:
        if "already exists" in e.gitOutput and "-b" in checkoutargs:
            if not quiet:
                logging.info(f"Reattempting checkout of previously existing branch {branch} without using a '-b' in {repo}")
            git.checkout(f"{checkoutargs.replace('-b','')} {branch}", execution_path=repo)
        else:
            logging.debug(f"checkout failed in {repo}.")
            raise e
    if verbose:
        logging.info(f"Checked out {branch} in {repo}")

    return True

_skipBranchCreation = False
_createNewBranch = False
_skipPush = False

def handleCheckoutMRE(mre):
    global _skipBranchCreation
    global _createNewBranch
    global _skipPush
    newBranchReposArgTuples = []

    for e1, branch, project, checkoutargs in zip(mre.exceptions(), mre.branches(), mre.repos(), mre.args()):
        try:
            raise e1
        except grape_errors.GrapeGitError as e:
            if "pathspec" in e.gitOutput.lower():
                createNewBranch = _createNewBranch
                if _skipBranchCreation:
                    logging.info(f"Skipping checkout of {branch} in " +
                                 f"{project}")
                    createNewBranch = False

                elif not createNewBranch:
                    createNewBranch = utility.userInput(
                        "Branch not found locally or remotely. Would you "+
                        f"like to create a new branch called {branch} " +
                        f"in {project}? \n(select 'a' to say yes for"+
                        " (a)ll, 's' to (s)kip creation for branches that"+
                        " don't exist )\n(y,n,a,s)", 'y', ['a','s'])

                if str(createNewBranch).lower()[0] == 'a':
                    _createNewBranch = True
                    createNewBranch = True
                if str(createNewBranch).lower()[0] == 's':
                    _skipBranchCreation = True
                    createNewBranch = False
                if createNewBranch:
                    newBranchReposArgTuples.append((project, branch, {"checkout": checkoutargs["checkout"], "skippush": _skipPush, "quiet":checkoutargs["quiet"], "verbose":checkoutargs["verbose"]}))
                else:
                    continue

            elif "already exists" in e.gitOutput.lower():
                if not checkoutargs["quiet"]:
                    logging.info(f"Branch {branch} already exists in " +
                                 f"{project}.")
                branchDescription = git.commitDescription(branch, execution_path=project)
                headDescription = git.commitDescription("HEAD", execution_path=project)
                if branchDescription == headDescription:
                    if not checkoutargs["quiet"]:
                        logging.info(f"Branch {branch} and HEAD are the " +
                                     f"same. Switching to {branch}.")
                    action = "k"
                else:
                    if not checkoutargs["quiet"]:
                        logging.info(f"Branch {branch} and HEAD " +
                                              "are not the same.")
                    action = ''
                    valid = False
                    while not valid:
                        action = utility.userInput(
                            f"Would you like to\n(k)eep it as is at: " +
                            f"{branchDescription}\n or \n (f)orce " +
                            f"it to: {headDescription}?\n(k,f)", 'k')
                        valid = (action == 'k') or (action == 'f')
                        if not valid:
                            logging.info("Invalid input. Enter k or f. ")
                if action == 'k':
                    git.checkout(branch, execution_path=project)
                elif action == 'f':
                    git.checkout(f"-B {branch}", execution_path=project)
            elif e.has_conflict():
                logging.info("CONFLICT occurred when pulling {branch} " +
                             "from origin.")
            elif "does not appear to be a git repository" in e.gitOutput.lower():
                if not checkoutargs["quiet"]:
                    logging.info("Remote 'origin' does not exist. "
                                 "This branch was not updated from a remote repository.")
            elif e.could_not_find_remote_ref():
                if not checkoutargs["quiet"]:
                    logging.info(
                        f"Remote of {project} does not have reference to " +
                        f"{branch}. You may want to push this branch. ")
            else:
                raise e

    if newBranchReposArgTuples:
        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
            createNewBranches,
            listOfRepoBranchArgTuples=newBranchReposArgTuples,
            workspace_dir=mre.workspace_dir)
        launcher.launchFromWorkspaceDir(handleMRE=createNewBranchesMREHandler)

def handleCheckoutSkipBranchCreationMRE(mre):
    global _skipBranchCreation
    _skipBranchCreation = True
    handleCheckoutMRE(mre)
    _skipBranchCreation = False

def handleCheckoutSkipBranchPushMRE(mre):
    global _skipPush
    _skipPush = True
    handleCheckoutMRE(mre)
    _skipPush = False

def createNewBranches(repo='', branch='', args={}, *, workspace_dir):
    #workspace_dir ignored
    checkoutargs = args["checkout"]
    skippusharg = args["skippush"]
    quiet = args["quiet"]
    verbose = args["verbose"]
    if verbose:
        logging.info(f"Checking out new branch {branch} in {repo}.")
    git.checkout(f"{checkoutargs} -b {branch}", execution_path=repo)
    if not skippusharg:
        git.push(f"-u origin {branch}", execution_path=repo)
    return True

def createNewBranchesMREHandler(mre):
    for e, b in zip(mre.exceptions(), mre.branches()):
        logging.error(f"{b} {e}")

# check whether the branch exists already in the outer level repo
# return value 0 : does not exist
#              1 : already exists
#              2 : exists as a case-insensitive match
def branchAlreadyExists(branch, workspace_dir):
    retVal = 0
    git.fetch("origin", execution_path=workspace_dir)
    # Trailing '' used to add a delimiter to end of path.
    branch_path = git.join_list_as_git_path(['remotes', 'origin', ''])
    # make sure branch does not already exist
    allBranches = set([b[len(branch_path):] if b.startswith(branch_path) else b for b in git.allBranches(execution_path=workspace_dir)])
    if branch in allBranches:
        logging.info(f"Branch {branch} already exists!")
        retVal = 1
    else:
        # make sure branch is not a case-insensitive match
        # as this will cause problems on Windows and Mac filesystems.
        for b in allBranches:
            if branch.lower() == b.lower():
                logging.info(f"Branch {b} already exists!\n" +
                             f"{branch} is a case insensitive match.")
                retVal = 2
    return retVal

def _submodulePathInfoForRevision(revision, *, workspace_dir):
    # We need both the stable submodule name and the path/url mapping to
    # distinguish true add/remove events from path-only moves.
    gitmodulesContents = git.show(f"{revision}:.gitmodules",
                                  execution_path=workspace_dir)
    if not gitmodulesContents:
        return {}, {}
    parsedSubmodules = submodule_parser.parse_gitmodules(
        gitmodulesContents.splitlines())
    pathInfo = {}
    for name, info in parsedSubmodules.items():
        path = info.get("path")
        if path:
            pathInfo[path] = {"name": name, **info}
    return parsedSubmodules, pathInfo


def nestedSubprojectInfoForConfigString(configContents):
    """Parse nested subproject metadata from raw `.grapeconfig` contents."""
    config = config_parser_base.GrapeConfigParserBase(
        configString=configContents if configContents else "")
    nestedProjects = {}
    for proj in config.getAllNestedSubprojects():
        nestedProjects[proj] = {
            "prefix": config.get(f"nested-{proj}", "prefix"),
            "url": config.get(f"nested-{proj}", "url"),
        }
    return config, nestedProjects


def nestedSubprojectInfoForRevision(revision, *, workspace_dir):
    """Return parsed `.grapeconfig` state for nested subprojects at `revision`.

    The mapping is keyed by nested subproject name and currently carries the
    fields we need for change detection: `prefix` and `url`.
    """
    configContents = git.show(f"{revision}:.grapeconfig",
                              execution_path=workspace_dir)

    return nestedSubprojectInfoForConfigString(configContents)


def parseGrapeConfigNestedProjectDiffOutput(currentRevision, targetRevision,
                                            *, workspace_dir):
    """Compute nested subproject add/remove/URL-replacement sets between revisions.

    This mirrors `parseGitModulesDiffOutput`, but for grape-managed nested
    subprojects declared in `.grapeconfig`.
    """
    try:
        nestedProjectListWillChange = ".grapeconfig" in git.diff(
            f"--name-only {currentRevision} {targetRevision}",
            execution_path=workspace_dir)
    except grape_errors.GrapeGitError as e:
        if f"bad revision '{targetRevision}'" in e.gitOutput:
            logging.info(f"Fetching {targetRevision} in {workspace_dir}")
            if targetRevision.startswith("origin/"):
                git.fetch("origin", targetRevision[len("origin/"):],
                          execution_path=workspace_dir)
            else:
                git.fetch("origin", f"{targetRevision}:{targetRevision}",
                          execution_path=workspace_dir)
            nestedProjectListWillChange = ".grapeconfig" in git.diff(
                f"--name-only {currentRevision} {targetRevision}",
                execution_path=workspace_dir)
        else:
            raise

    if not nestedProjectListWillChange:
        emptyConfig = config_parser_base.GrapeConfigParserBase(configString="")
        return emptyConfig, emptyConfig, set(), set(), set()

    previousConfig, previousNestedProjects = nestedSubprojectInfoForRevision(
        currentRevision, workspace_dir=workspace_dir)
    targetConfig, targetNestedProjects = nestedSubprojectInfoForRevision(
        targetRevision, workspace_dir=workspace_dir)

    previousSet = set(previousNestedProjects)
    targetSet = set(targetNestedProjects)
    removedProjects = previousSet - targetSet
    addedProjects = targetSet - previousSet
    replacedProjects = {
        proj for proj in previousSet.intersection(targetSet)
        if previousNestedProjects[proj]["url"] != targetNestedProjects[proj]["url"]
    }

    return (previousConfig, targetConfig, addedProjects,
            removedProjects, replacedProjects)


def preflightReplacedNestedSubprojects(previousConfig, targetConfig,
                                       replacedProjects, *, workspace_dir, branch,
                                       force=False):
    """Collect approval for nested subprojects whose URL changed.

    The result is a plan consumed later by `applyReplacedNestedSubprojects`.
    Returning `None` means at least one required replacement was rejected, so
    the caller should abort before mutating the workspace.
    """
    userConfig = config_parser_user.GrapeConfigParserUser(
        workspace_dir=workspace_dir)
    replacementPlan = {}

    for proj in sorted(replacedProjects):
        nestedProj = f"nested-{proj}"
        oldPrefix = previousConfig.get(nestedProj, "prefix")
        newPrefix = targetConfig.get(nestedProj, "prefix")
        oldUrl = previousConfig.get(nestedProj, "url")
        newUrl = targetConfig.get(nestedProj, "url")
        working_directory = os.path.join(workspace_dir, oldPrefix)
        dirExists = os.path.exists(working_directory)
        wasActive = userConfig.getboolean(nestedProj, "active")
        worktreeClean = (not dirExists or
                         git.isWorkingDirectoryClean(
                             execution_path=working_directory))

        removeExisting = dirExists
        reactivate = wasActive
        if not removeExisting and not reactivate:
            replacementPlan[proj] = {
                "removeExisting": False,
                "reactivate": False,
            }
            continue

        # Non-forced operation still allows the user to approve replacing a
        # dirty nested subproject before any workspace mutation happens.
        if not force:
            default = 'y'

            if not dirExists: # wasActive must be true or we would have hit the continue above
                repo_status = "\nThe workspace directory is missing, so there is nothing to remove."
            else:
                # Check to see if it is safe to remove the old repo by default
                repo_status = ""
                # Check for clean workspace
                if not worktreeClean:
                    repo_status += f"\nRepo contains local changes that will be lost!"
                    default = 'n'
                # Check for branches that are ahead of their remote tracking branches.
                # Note this will not detect branches that have never been pushed.
                branchList = git.branch("-vv", execution_path=working_directory) 
                if re.search(r"\[.*: ahead .*\]", branchList):
                    repo_status += f"\nRepo contains some branches that are ahead of their tracking branches:"
                    default = 'n'
                    for line in branchList.splitlines():
                        if re.search(r"\[.*: ahead .*\]", line):
                            repo_status += f"\n   {line}"
                # Check if this branch has diffs compared to the public branch
                public = config_parser_workspace.GrapeConfigParserWorkspace(workspace_dir).getPublicBranchFor(branch)
                if public != branch:
                    diff = git.diff(f"--name-only {branch} {public} --", execution_path=working_directory)
                    if diff:
                        repo_status += f"\n{branch} contains changes relative to {public}:"
                        for line in diff.splitlines()[:10]:
                            repo_status += f"\n   {line}"
                        default = 'n'
            prompt = (
                f"Nested subproject {oldPrefix} is changing URL\n"
                f"   from {oldUrl}\n   to {newUrl}.\nGRAPE must remove the current "
                f"checkout and recreate it"
                f"{' at ' + newPrefix if newPrefix != oldPrefix else ''}.\n"
                f"If your branch does not exist in the new repo, you will have to run grape uv afterwards."
                f"{repo_status}"
                "\nProceed? [y/n]"
            )

            approved = utility.userInput(prompt, default)
            if not approved:
                logging.info(f"{oldPrefix} must be replaced before proceeding!")
                return None

        replacementPlan[proj] = {
            "removeExisting": removeExisting,
            "reactivate": reactivate,
        }

    return replacementPlan


def applyReplacedNestedSubprojects(previousConfig, replacedProjects,
                                   replacementPlan, branch, filterArg,
                                   targetConfig=None,
                                   *, workspace_dir):
    """Apply a previously approved nested-subproject replacement plan.

    This runs only after checkout/merge has produced the target top-level
    branch state, so activation uses the new `.grapeconfig` URL while removal
    still uses the old prefix metadata from `previousConfig`.
    """
    userConfig = config_parser_user.GrapeConfigParserUser(
        workspace_dir=workspace_dir)
    rmArgs = {"-F": True, "-v": False}

    for proj in sorted(replacedProjects):
        if proj not in replacementPlan:
            logging.error(
                f"No approved replacement plan recorded for nested "
                f"subproject {proj}.")
            return False

        projPrefix = previousConfig.get(f"nested-{proj}", "prefix")
        plan = replacementPlan[proj]
        if plan["removeExisting"]:
            logging.info(f"Removing Nested Subproject {projPrefix}")
            if not UpdateView.deactivateNestedSubproject(
                    proj, userConfig, workspace_dir, rmArgs,
                    config=previousConfig):
                logging.info(f"Failed to remove {projPrefix}!")
                return False

        if plan["reactivate"]:
            logging.info(f"Activating Nested Subproject {projPrefix} on {branch}")
            if targetConfig is not None:
                activated = AddSubproject.activateNestedSubprojectForConfig(
                    proj, targetConfig, userConfig, branch, filterArg,
                    workspace_dir=workspace_dir)
            else:
                activated = AddSubproject.activateNestedSubproject(
                    proj, userConfig, branch, filterArg, workspace_dir)
            if not activated:
                logging.info(f"Failed to activate {proj}.\nExiting...")
                return False

    return True


def parseGitModulesDiffOutput(currentSHA, branch, addedModules, removedModules,
                              changedURLModules, movedModules=None,
                              *, workspace_dir):
    try:
        submoduleListWillChange = ".gitmodules" in git.diff(f"--name-only {currentSHA} {branch} --", execution_path=workspace_dir)
    except grape_errors.GrapeGitError as e:
        if f"bad revision '{branch}'" in e.gitOutput:
            logging.info(f"Fetching {branch} in {workspace_dir}")
            if branch.startswith("origin/"):
                git.fetch("origin", branch[len("origin/"):],
                          execution_path=workspace_dir)
            else:
                git.fetch("origin", f"{branch}:{branch}",
                          execution_path=workspace_dir)
            submoduleListWillChange = ".gitmodules" in git.diff(f"--name-only {currentSHA} {branch} --", execution_path=workspace_dir)
        else:
            raise e
    if submoduleListWillChange:
        previousParsed, previousByPath = _submodulePathInfoForRevision(
            currentSHA, workspace_dir=workspace_dir)
        branchParsed, branchByPath = _submodulePathInfoForRevision(
            branch, workspace_dir=workspace_dir)

        previousPaths = set(previousByPath)
        branchPaths = set(branchByPath)
        addedPaths = branchPaths - previousPaths
        removedPaths = previousPaths - branchPaths

        for path in sorted(previousPaths.intersection(branchPaths)):
            previousUrl = previousByPath[path].get("url")
            branchUrl = branchByPath[path].get("url")
            if previousUrl != branchUrl:
                changedURLModules.append(path)

        if movedModules is not None:
            # Prefer Git's rename detection when available so an actual file
            # move of the gitlink shows up as a move instead of add/remove.
            renameOutput = git.diff(f"--name-status -M {currentSHA} {branch} --",
                                    execution_path=workspace_dir)
            for line in renameOutput.splitlines():
                fields = line.split('\t')
                if len(fields) != 3 or not fields[0].startswith('R'):
                    continue
                oldPath, newPath = fields[1], fields[2]
                if oldPath not in removedPaths or newPath not in addedPaths:
                    continue
                previousInfo = previousByPath.get(oldPath, {})
                branchInfo = branchByPath.get(newPath, {})
                if previousInfo.get("url") != branchInfo.get("url"):
                    continue
                movedModules[oldPath] = newPath
                removedPaths.discard(oldPath)
                addedPaths.discard(newPath)

            # Fall back to matching the logical submodule name in .gitmodules.
            # This catches path-only moves even if Git does not emit an R entry.
            for name in sorted(set(previousParsed).intersection(branchParsed)):
                previousInfo = previousParsed[name]
                branchInfo = branchParsed[name]
                oldPath = previousInfo.get("path")
                newPath = branchInfo.get("path")
                if not oldPath or not newPath or oldPath == newPath:
                    continue
                if previousInfo.get("url") != branchInfo.get("url"):
                    continue
                movedModules.setdefault(oldPath, newPath)
                removedPaths.discard(oldPath)
                addedPaths.discard(newPath)

            # Some repos use the path itself as the .gitmodules section name,
            # so a move also changes the logical name. Pair unique add/remove
            # candidates by URL to catch those path+name renames.
            removedByUrl = defaultdict(list)
            addedByUrl = defaultdict(list)
            for oldPath in removedPaths:
                url = previousByPath.get(oldPath, {}).get("url")
                if url:
                    removedByUrl[url].append(oldPath)
            for newPath in addedPaths:
                url = branchByPath.get(newPath, {}).get("url")
                if url:
                    addedByUrl[url].append(newPath)

            for url in sorted(set(removedByUrl).intersection(addedByUrl)):
                oldMatches = removedByUrl[url]
                newMatches = addedByUrl[url]
                if len(oldMatches) != 1 or len(newMatches) != 1:
                    logging.warning(
                        "Ambiguous submodule move detection for URL "
                        f"{url}. Removed paths: {sorted(oldMatches)}. "
                        f"Added paths: {sorted(newMatches)}. Skipping "
                        "inferred move.")
                    continue
                oldPath = oldMatches[0]
                newPath = newMatches[0]
                movedModules.setdefault(oldPath, newPath)
                removedPaths.discard(oldPath)
                addedPaths.discard(newPath)

        addedModules.extend(sorted(addedPaths))
        removedModules.extend(sorted(removedPaths))

    return addedModules, removedModules, changedURLModules

def cleanSubmodule(sub, args, veryclean = False, activeSubmodules = [], *, workspace_dir):
    cleaned = False
    working_dir = os.path.join(workspace_dir, sub)
    dirExists = os.path.exists(working_dir)
    dirIsEmpty = not dirExists or len(os.listdir(working_dir)) == 0
    workingDirClean = dirIsEmpty or git.isWorkingDirectoryClean(execution_path=working_dir)
    changedActive = sub in activeSubmodules
    force = veryclean or args["-F"] or args["-f"]

    if force or workingDirClean or (veryclean and not changedActive):
        # veryclean will always try to clean, fail if the clean fails
        # and remove the back-end repo.
        if veryclean:
            unpushed = False
            if not dirIsEmpty and changedActive:
                unpushed = git.log("--branches --not --remotes --oneline --decorate", execution_path=working_dir)
            if unpushed and not force:
                logging.info("You have unpushed changed in " +
                             f"{sub}:\n{unpushed}")
                clean = utility.userInput(
                    f"Would you like to remove the submodule {sub} " +
                    "(this will discard your unpushed changes)?", 'n')
            else:
                clean = True
        else:
            cleanBehaviorSet = args["--noUpdateView"] or args["--updateView"]
            if not cleanBehaviorSet and not force:
                clean = utility.userInput("Would you like to remove " +
                                          f"the submodule {sub} ?", 'n')
            elif args["--noUpdateView"]:
                clean = False
            elif args["--updateView"]:
                clean = True
            else:
                clean = False
        if clean:
            logging.info(f"Removing {'clean ' if not force else ''}submodule {sub}.")
            if not veryclean or changedActive:
                try:
                    shutil.rmtree(os.path.join(workspace_dir, sub))
                except FileNotFoundError:
                    pass
            if veryclean:
                if changedActive:
                    git.submodule(f"deinit -f {sub}", execution_path=workspace_dir)
                # This must be removed even for inactive submodules
                modulepath = os.path.join(workspace_dir, ".git", "modules", sub)
                if os.path.exists(modulepath):

                    try:
                        shutil.rmtree(modulepath)
                    except OSError:
                        # windows needs to change the permissions first
                        for root,dirs,files in os.walk(modulepath):
                            for name in files:
                                os.chmod(os.path.join(root, name), stat.S_IWRITE)
                        try:
                            shutil.rmtree(modulepath)
                        except OSError:
                            time.sleep(1)
                            shutil.rmtree(modulepath)
            cleaned = True
    else:
        logging.info(f"Unstaged / committed changes in {sub}," +
                     " not removing.")
    return cleaned

def _mergedWorkspaceHasSubmodule(path, *, workspace_dir):
    # Query the post-merge/post-checkout .gitmodules view. The move detector is
    # intentionally conservative: we only apply the local filesystem move when
    # the merged workspace actually expects the destination path to exist.
    return path in git.getAllSubmodules(execution_path=workspace_dir)


def _refreshMovedSubmoduleConfig(sub, *, workspace_dir):
    if not _mergedWorkspaceHasSubmodule(sub, workspace_dir=workspace_dir):
        logging.info(
            f"Merged workspace does not contain submodule {sub}. "
            "Skipping submodule init/sync for the local move.")
        return
    try:
        git.submodule(f"init -- {sub}", execution_path=workspace_dir)
        git.submodule(f"sync -- {sub}", execution_path=workspace_dir)
    except grape_errors.GrapeGitError as e:
        if ("pathspec" in e.gitOutput.lower() or
                "no submodule mapping found in .gitmodules" in
                e.gitOutput.lower()):
            logging.info(
                f"Unable to refresh submodule metadata for {sub} after the "
                "local move. Skipping init/sync.")
            return
        raise


def _movesPresentInWorkspace(movedModules, *, workspace_dir):
    # Filter inferred moves against the branch/merge result that is now checked
    # out in the workspace.
    #
    # Example:
    #   topic branch:      tpl/foo
    #   older branch:      exports/foo
    #
    # If we merge the older branch and the result still contains
    # tpl/foo in .gitmodules, then this is not a local move to apply
    # anymore. Treating tpl/foo -> exports/foo as a completed local
    # move would break later bookkeeping and can trigger git submodule commands
    # for a path that the merged workspace does not actually contain.
    currentSubmodules = set(git.getAllSubmodules(execution_path=workspace_dir))
    filteredMoves = {}
    for oldSub, newSub in movedModules.items():
        if newSub in currentSubmodules and oldSub not in currentSubmodules:
            filteredMoves[oldSub] = newSub
        elif oldSub in currentSubmodules and newSub not in currentSubmodules:
            logging.debug(
                f"Merged workspace still contains submodule {oldSub}. "
                f"Skipping local move to {newSub}.")
        else:
            logging.debug(
                f"Merged workspace does not contain a unique destination for "
                f"submodule move {oldSub} -> {newSub}. Skipping local move.")
    return filteredMoves


def moveSubmodule(oldSub, newSub, *, workspace_dir, force=False):
    oldWorkingDir = os.path.join(workspace_dir, oldSub)
    newWorkingDir = os.path.join(workspace_dir, newSub)

    # Checkout may already have materialized the new path. In that case there
    # is nothing left for the local move step to do.
    if not os.path.exists(oldWorkingDir):
        return True
    if os.path.exists(newWorkingDir):
        if os.path.isdir(newWorkingDir) and len(os.listdir(newWorkingDir)) == 0:
            os.rmdir(newWorkingDir)
        else:
            logging.info(
                f"Destination for moved submodule already exists at "
                f"{newSub}. Not moving.")
            return False
    if not force and not git.isWorkingDirectoryClean(execution_path=oldWorkingDir):
        logging.info(f"Unstaged / committed changes in {oldSub}, not moving.")
        return False

    gitdir = git.gitDir(execution_path=oldWorkingDir)
    if not gitdir:
        return False
    gitdir = os.path.normpath(gitdir)
    newGitdirPath = os.path.join(workspace_dir, ".git", "modules", newSub)

    if gitdir != newGitdirPath:
        if os.path.exists(newGitdirPath):
            # A prior failed move/retry may already have created the new
            # backend path. If the new worktree does not exist yet, prefer the
            # old backend repo and replace the stale destination backend.
            if os.path.exists(newWorkingDir):
                logging.info(
                    f"Destination gitdir for moved submodule already exists "
                    f"at {newSub}. Not moving.")
                return False
            try:
                shutil.rmtree(newGitdirPath)
            except OSError:
                for root, dirs, files in os.walk(newGitdirPath):
                    for name in files:
                        os.chmod(os.path.join(root, name), stat.S_IWRITE)
                shutil.rmtree(newGitdirPath)
        os.makedirs(os.path.dirname(newGitdirPath), exist_ok=True)
        os.rename(gitdir, newGitdirPath)
        gitdir = newGitdirPath

    os.makedirs(os.path.dirname(newWorkingDir), exist_ok=True)
    os.rename(oldWorkingDir, newWorkingDir)

    # The submodule backend repo usually stays in .git/modules/<old-path>, so
    # update the frontend gitfile and backend core.worktree to point at the
    # new working tree location.
    newGitdir = os.path.relpath(gitdir, newWorkingDir).replace(os.sep, '/')
    with open(os.path.join(newWorkingDir, ".git"), "w") as gitfile:
        gitfile.write(f"gitdir: {newGitdir}\n")

    moduleConfigPath = os.path.join(gitdir, "config")
    if os.path.exists(moduleConfigPath):
        newWorktree = os.path.relpath(newWorkingDir, gitdir).replace(os.sep, '/')
        git.config(f"--file {shlex.quote(moduleConfigPath)} core.worktree",
                   newWorktree, execution_path=workspace_dir)

    # Refresh local submodule config for the new path after the filesystem move.
    _refreshMovedSubmoduleConfig(newSub, workspace_dir=workspace_dir)
    return True


def applyMovedSubmodules(movedModules, *, workspace_dir, force=False):
    successfulMoves = {}
    failedMoves = {}
    for oldSub, newSub in _movesPresentInWorkspace(
            movedModules, workspace_dir=workspace_dir).items():
        logging.info(f"Moving submodule {oldSub} to {newSub}.")
        if moveSubmodule(oldSub, newSub, workspace_dir=workspace_dir, force=force):
            successfulMoves[oldSub] = newSub
        else:
            failedMoves[oldSub] = newSub
    return successfulMoves, failedMoves


def shouldParallelizeSubmoduleCleanup(sub, args, veryclean=False,
                                      activeSubmodules=None, *, workspace_dir):
    if activeSubmodules is None:
        activeSubmodules = []

    force = args["-F"] or args["-f"]
    working_dir = os.path.join(workspace_dir, sub)
    dirExists = os.path.exists(working_dir)
    dirIsEmpty = not dirExists or len(os.listdir(working_dir)) == 0
    changedActive = sub in activeSubmodules

    if veryclean:
        if not changedActive:
            return True
        if dirIsEmpty:
            return True
        if not force and not git.isWorkingDirectoryClean(execution_path=working_dir):
            return False
        unpushed = git.log("--branches --not --remotes --oneline --decorate",
                           execution_path=working_dir)
        return not bool(unpushed)

    if not dirExists or dirIsEmpty:
        return args["--updateView"]

    if not force and not git.isWorkingDirectoryClean(execution_path=working_dir):
        return False

    return args["--updateView"]


def launcherCleanSubmodule(repo='', branch='', args=None, *, workspace_dir):
    # 'branch' included for continuity with multi_repo_cmd_launcher.
    sub = os.path.relpath(repo, workspace_dir)
    return cleanSubmodule(sub, args["checkoutArgs"], args["veryclean"],
                          args["activeSubmodules"], workspace_dir=workspace_dir)


def parallelCleanSubmodules(submodules, args, veryclean=False,
                            activeSubmodules=None, *, workspace_dir):
    if activeSubmodules is None:
        activeSubmodules = []

    autoCleanSubmodules = []
    serialCleanSubmodules = []

    for sub in submodules:
        if shouldParallelizeSubmoduleCleanup(
                sub, args, veryclean, activeSubmodules,
                workspace_dir=workspace_dir):
            autoCleanSubmodules.append(sub)
        else:
            # Keep prompting / dirty-worktree cases on the serial path so the
            # existing interactive behavior remains unchanged.
            serialCleanSubmodules.append(sub)

    failedSubmodules = []
    if autoCleanSubmodules:
        launchTuples = [(sub, '',
                         {"checkoutArgs": args,
                          "veryclean": veryclean,
                          "activeSubmodules": activeSubmodules})
                        for sub in autoCleanSubmodules]
        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
            launcherCleanSubmodule,
            listOfRepoBranchArgTuples=launchTuples,
            workspace_dir=workspace_dir)
        retvals = launcher.launchFromWorkspaceDir(noPause=True)
        failedSubmodules.extend(
            sub for sub, cleaned in zip(autoCleanSubmodules, retvals)
            if not cleaned)

    return failedSubmodules, serialCleanSubmodules


class Checkout(Option, WorkspaceDirHandler):
    """
    grape checkout

    Usage: grape-checkout [-v] [-q] [-b] [-f] [-F] [--sync=<bool>] [--emailSubject=<sbj>] [--updateView] [--noUpdateView] [--filter=<arg>] <branch>

    Options:
        -v                  Print output from individual directories.
        -q                  Quiet warnings from individual directories that don't cause failure.
        -b                  Create the branch off of the current HEAD in each project.
        -f                  Force removal of submodules that are removed or replaced (with a different URL) by the checkout.
                            Nested subproject changes still prompt the user.
        -F                  Force removal of submodules or nested subprojects that are removed or replaced (with a different URL) 
                            by the checkout.
        --sync=<bool>       Take extra steps to ensure the branch you check out is up to date with origin,
                            either by pushing or pulling the remote tracking branch.
                            [default: .grapeconfig.post-checkout.syncWithOrigin]
        --updateView        If your submodules / nested projects change, change your workspace to match the changes.
                            Warning - setting this may cause you to lose unpushed work in nested subprojects.
        --noUpdateView      If your submodules / nested projects change, do not change your workspace to match the changes.
        --filter=<arg>      Optional clone filter argument to use if any subprojects get cloned during checkout.
                            WARNING! This is still experimental and may have issues with grape workflows.
                            In particular, tree:0 has performance issues with git rev-list/log command on specified
                            files (it appears to download each commit separately).
          

    Arguments:
        <branch>    The name of the branch to checkout.

    """
    def __init__(self):
        super(Checkout, self).__init__()
        self._key = "checkout"
        self._section = "Workspace"

    def description(self):
        return "Checks out a branch in all projects in this workspace."

    @log_wrapper
    def execute(self, args):
        # Imported here to avoid circular dependencies
        from vine import grapeMenu

        sync = args["--sync"].lower().strip() in ['true', 'yes']
        args["--sync"] = sync
        branch = args["<branch>"]

        if branch == "HEAD":
           logging.error("<branch> cannot be specified as HEAD")
           return False

        startingSHA = str(git.shortSHA(branchName="HEAD", execution_path=self.workspace_dir))

        addedModules = []
        removedModules = []
        changedURLModules = []
        movedModules = {}
        uvArgs = []
        checkoutargs = ''
        submodulesDidChange = False
        nestedProjectListDidChange = False
        addedProjects = set()
        removedProjects = set()
        replacedProjects = set()
        replacementPlan = {}
        previousConfig = config_parser_base.GrapeConfigParserBase(
            configString="")
        if args['-b']:
            checkoutargs += " -b"

            branchStatus = branchAlreadyExists(branch, self.workspace_dir)
            if branchStatus:
                logging.info("Not creating new branch.")
                return False
        else:
            # check to see if we already have the branch
            try:
                git.shortSHA(branchName=branch, execution_path=self.workspace_dir)
            except:
                try:
                    # otherwise fetch it
                    git.fetch("origin", f"{branch}:{branch}", execution_path=self.workspace_dir)
                except grape_errors.GrapeGitError as e:
                    logging.info(
                        f"Branch {branch} could not be fetched in outer " +
                        f"level repo:\n{e}\nUse grape checkout -b if" +
                        " you really want to create a new branch off of HEAD.")
                    return False

            previousConfig, branchConfig, addedProjects, removedProjects, replacedProjects = (
                parseGrapeConfigNestedProjectDiffOutput(
                    startingSHA, branch, workspace_dir=self.workspace_dir))
            nestedProjectListDidChange = bool(
                removedProjects or addedProjects or replacedProjects)
            if replacedProjects:
                replacementPlan = preflightReplacedNestedSubprojects(
                    previousConfig, branchConfig, replacedProjects,
                    workspace_dir=self.workspace_dir, branch=branch, force=args["-F"])
                if replacementPlan is None:
                    return False

            if config_parser_global.grapeConfig().getboolean(self.SECTION_WORKSPACE, "manageSubmodules"):
                parseGitModulesDiffOutput(
                    startingSHA, branch, addedModules, removedModules,
                    changedURLModules, movedModules,
                    workspace_dir=self.workspace_dir)

            if addedModules or removedModules or changedURLModules or movedModules:
                submodulesDidChange = True

            # deinit and clean out any submodules that changed urls
            initiallyActiveSubmodules = git.getActiveSubmodules(execution_path=self.workspace_dir)
            for sub in changedURLModules:
                maybe_active = "active" if sub in initiallyActiveSubmodules else "inactive"
                if not args["-q"]:
                    logging.info(
                        f"url for {sub} changed, attempting to remove " +
                        f"references for {maybe_active} submodule.")
            failedSubs, serialSubs = parallelCleanSubmodules(
                changedURLModules, args, True, initiallyActiveSubmodules,
                workspace_dir=self.workspace_dir)
            for sub in failedSubs:
                logging.info(f"Failed to remove old submodule for {sub}.")
                return False
            for sub in serialSubs:
                cleaned = cleanSubmodule(sub, args, True, initiallyActiveSubmodules, workspace_dir=self.workspace_dir)
                if not cleaned:
                    logging.info(f"Failed to remove old submodule for {sub}.")
                    return False

        logging.info(f"Performing checkout of {branch} in outer level project.")
        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
            handledCheckout,
            listOfRepoBranchArgTuples=[(self.workspace_dir, branch,
                                        {"checkout":checkoutargs, "sync":sync, "quiet":args["-q"], "verbose":args["-v"]})],
            workspace_dir=self.workspace_dir)

        retvals = launcher.launchFromWorkspaceDir(handleMRE=handleCheckoutMRE)
        if not retvals or not retvals[0]:
            return False

        # Ensure any global grape config is re-read from the new branch
        config_parser_global.read(workspace_dir=self.workspace_dir)

        if replacedProjects:
            if not applyReplacedNestedSubprojects(
                    previousConfig, replacedProjects, replacementPlan,
                    branch, args["--filter"], workspace_dir=self.workspace_dir):
                return False

        # reinit any submodules with changed urls
        for sub in changedURLModules:
            if sub in initiallyActiveSubmodules:
                git.submodule(f"init {sub}", execution_path=self.workspace_dir)

        movedModules, failedMoves = applyMovedSubmodules(
            movedModules, workspace_dir=self.workspace_dir, force=(args["-F"] or args["-f"]))
        for oldSub, newSub in failedMoves.items():
            # If the local move cannot be completed safely, fall back to the
            # existing remove/recreate path instead of aborting checkout.
            logging.info(f"Failed to move submodule {oldSub} to {newSub}; falling back to remove and re-add.")
            removedModules.append(oldSub)
            addedModules.append(newSub)

        # clean out removed submodules
        failedSubs, serialSubs = parallelCleanSubmodules(
            removedModules, args, workspace_dir=self.workspace_dir)
        for sub in serialSubs:
            cleanSubmodule(sub, args, workspace_dir=self.workspace_dir)

        if removedProjects:
            for proj in removedProjects:
                projPrefix = previousConfig.get(f"nested-{proj}", "prefix")

                # OK if directory does not exist as it may be removed soon.
                working_directory = os.path.join(self.workspace_dir, projPrefix)
                if not os.path.exists(working_directory):
                    continue

                if git.isWorkingDirectoryClean(execution_path=working_directory) or args["-F"]:
                    removeBehaviorSet = args["--noUpdateView"] or args["--updateView"]
                    if not removeBehaviorSet:
                        remove = args["-F"] or utility.userInput(f"Would you like to remove the nested subproject {projPrefix}? \nAll work that has not been pushed will be lost. ", 'n')
                    elif args["--noUpdateView"]:
                        remove = False
                    elif args["--updateView"]:
                        remove = True
                    if remove:
                        remove = args["-F"] or utility.userInput(f"Are you sure you want to remove {projPrefix}?", 'n')
                    if remove:
                        shutil.rmtree(os.path.join(self.workspace_dir, projPrefix))
                else:
                    if not args["-q"]:
                        logging.info(
                            f"Unstaged / committed changes in {projPrefix},"
                            " not removing. \nNote this project is NOT " +
                            f"active in {branch}. ")

        if not submodulesDidChange and not nestedProjectListDidChange:
            uvArgs.append("--checkSubprojects")
        else:
            updateViewSet = args["--noUpdateView"] or args["--updateView"]
            if not updateViewSet:
                updateView = utility.userInput("Submodules or subprojects were added/removed as a result of this checkout. \n" +
                                               "%s" % ("Added Projects: %s\n" % ','.join(addedProjects) if addedProjects else "") +
                                               "%s" % ("Added Submodules: %s\n"% ','.join(addedModules) if addedModules else "") +
                                               "%s" % ("Removed Projects: %s\n" % ','.join(removedProjects) if removedProjects else "") +
                                               "%s" % ("Removed Submodules: %s\n" % ','.join(removedModules) if removedModules else "") +
                                               "%s" % ("Moved Submodules: %s\n" % ','.join([f"{old}->{new}" for old, new in movedModules.items()]) if movedModules else "") +
                                               "%s" % ("Replaced Projects: %s\n" % ','.join(replacedProjects) if replacedProjects else "") +
                                               "Would you like to update your workspace view? [y/n]", 'n')
            elif args["--noUpdateView"]:
                updateView = False
            elif args["--updateView"]:
                updateView = True
            if not updateView:
                uvArgs.append("--checkSubprojects")

        if args["-b"]:
            uvArgs.append("-b")
        if sync:
            uvArgs.append("--sync=True")
        else:
            uvArgs.append("--sync=False")
            uvArgs.append("--skipBranchPush")

        if args["--filter"]:
            uvArgs.append("--filter="+args["--filter"])

        # in case the user switches to a branch without corresponding branches in the submodules, make sure active submodules
        # are at the right commit before possibly creating new branches at the current HEAD.
        git.submodule("update", execution_path=self.workspace_dir)
        logging.info(f"Calling grape uv {' '.join(uvArgs)} to ensure" +
                     " branches are consistent across all active" +
                     " subprojects and submodules.")
        menu = grapeMenu.menu(workspace_dir=self.workspace_dir)
        menu.applyMenuChoice('uv', uvArgs)

        if sync:
            logging.info(
                f"Switched to {branch}. Updating from remote...\n\t (use"+
                " --sync=False or .grapeconfig.post-checkout.syncWithOrigin" +
                " to change behavior.)")
            if args["-b"]:
                menu.applyMenuChoice("push")
            else:
                menu.applyMenuChoice("pull")
        else:
            logging.info(f"Switched to {branch}.")

        global _skipBranchCreation
        global _createNewBranch
        _skipBranchCreation = False
        _createNewBranch = False
        return True

    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_POST_CHECKOUT)
        config.set(self.SECTION_POST_CHECKOUT, "syncWithOrigin", "True")
