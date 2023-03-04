import json
import logging
import os
import shutil
import stat
from vine import addSubproject
from vine import checkout
from vine import config_parser_global
from vine import config_parser_user
from vine import config_parser_workspace
from vine import grape_errors
from vine import grapeGit as git
from vine import multi_repo_cmd_launcher
from vine import utility
from vine import vine_subprocess
from vine.vine_logging import log_wrapper
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.option import Option

try:
    import tkinter as Tk
    TkinterImportError = None
except ImportError as e:
    TkinterImportError = e


# update your custom sparse checkout view
class UpdateView(Option, WorkspaceDirHandler):
    """
    grape uv  - Updates your active submodules and ensures you are on a consistent branch throughout your project.
    Usage: grape-uv [-f] [-F] [--checkSubprojects] [-b] [--gui] [--skipTopLevel]
                    [--skipSubmodules | --allSubmodules | --noSubmodules]
                    [--skipNestedSubprojects | --allNestedSubprojects | --noNestedSubprojects]
                    [--sync=<bool>] [--skipSubmoduleSwitch] [--skipBranchCreation] [--branchName=<branchName>]
                    [--add=<addedSubmoduleOrSubproject>...] [--rm=<removedSubmoduleOrSubproject>...]
                    [--generateSHAList] [--ensureCIReposPresent] [--verifySHAList]
                    [--branchFilter=<branch> | --branchChanged=<branch>[~]]
                    [--updateRemoteProtocol]
                    [--spackEnv]
           grape-uv --checkRemoteSubmodules [--branchName=<name>] [--allSubmodules]

    Options:
        -f                           Force removal of submodules currently in your view that are taken out of the view
                                     as a result to this call to uv.
        -F                           Force removal of nested subprojects currently in your view that are taken out of the
                                     view as a result to this call to uv.
        --checkSubprojects           Checks for branch model consistency across your submodules and subprojects, but does
                                     not go through the 'which submodules do you want' script.
        --checkRemoteSubmodules      Checks for branch model consistency across your submodules only, looking only at the
                                     remote submodule repos. Only submodules in the workspace are checked
                                     unless --allSubmodules is specified, 
        -b                           Automatically creates subproject branches that should be there according to your
                                     branching model.
        --skipTopLevel               Skip top level repository for syncing and checking.
        --skipSubmodules             Skip all submodules (leaving them untouched).
        --allSubmodules              Automatically add all submodules from your workspace. This can be subsequently
                                     modified by --branchFilter, --branchChanged, or --rm.
        --noSubmodules               Remove all submodules to your workspace. This can be subsequently
                                     modified by --add or --ensureCIReposPresent.
        --skipNestedSubprojects      Skip all nested subprojects (leaving them untouched).
        --allNestedSubprojects       Automatically add all nested subprojects to your workspace. This can be subsequently
                                     modified by --branchFilter, --branchChanged, or --rm.
        --noNestedSubprojects        Remove all nested subprojects from your workspace. This can be subsequently
                                     modified by --add or --ensureCIReposPresent.
        --sync=<bool>                Take extra steps to ensure the branch you're on is up to date with origin,
                                     either by pushing or pulling the remote tracking branch.
                                     This will also checkout the public branch in a headless state prior to offering to
                                     create a new branch (in repositories where the current branch does not exist).
                                     [default: .grapeconfig.post-checkout.syncWithOrigin]
        --skipSubmoduleSwitch        Skip switch to public branch in submodules if branches doesn't exist.
        --skipBranchCreation         Skip creation of branches that don't exist.
        --branchName=<name>          Override the branch name
        --add=<project>              Submodule or subproject to add to the workspace. Can be defined multiple times.
        --rm=<project>               Submodule or subproject to remove from the workspace. Can be defined multiple times.
        --gui                        Use the graphical user interface to select your view.
        --generateSHAList            Dump current nested subproject and topLevel repo SHAs to GRAPE_PROJECT_SHA.json.
        --verifySHAList              Verify current state is consistent with state in a file generated by --generateSHAList.
        --ensureCIReposPresent       Ensure any repos listed in .grapeconfig.workspace.CIRepos are present in the workspace
        --branchFilter=<branch>      Filter workspace by repos that currently have a branch matching branch, removing or
                                     deactivating repositories that do not have the branch stored on their remote.
        --branchChanged=<branch>[~]  Filter workspace by repos that currently have a branch matching <branch> and where
                                     that branch is changed relative to the public branch, removing or deactivating repositories
                                     that are not changed.
                                     If a tilde (~) follows <branch>, the branch is not considered changed in a subproject
                                     if the SHA of the branch is tagged by a tag (e.g. <tagPrefix><version>.<version>) that
                                     matches the tag of the public branch (except for the final version slot) or in a submodule
                                     if the SHA of the branch is in the history of the gitlink.
        --updateRemoteProtocol       Update subprojects whose remotes use a different protocol from the outer level
                                     repository. These subprojects are updated by recloning using the protocol of the outer
                                     level repo.
        --spackEnv                   Spack Develop Environment build option 

        If --allSubmodules, --noSubmodules, --allNestedSubprojects, --noNestedSubprojects, --branchFilter, --branchChanged,
        --add, --rm, or --ensureCIReposPresent is specified, the workspace will be updated without user intervention. In this
        non-interactive mode, the operations are applied in the following order:
            1) --allSubmodules, --noSubmodules, --allNestedSubprojects, --noNestedSubprojects
            2) --branchFilter/--branchChanged
            3) --add, --rm, --ensureCIReposPresent

    """
    def __init__(self):
        super(UpdateView, self).__init__()
        self._key = "uv"
        self._section = "Workspace"
        self._pushBranch = False
        self._skipPush = False
        self.uvManager = None

    def description(self):
        return "Update the view of your current working tree"

    def defineActiveSubprojects(self, projectType="submodule"):
        """
        Queries the user for the submodules (projectType == "submodule") or nested subprojects
        (projectType == "nested subproject") they would like to activate.

        """
        if projectType == "submodule":
            allSubprojects = git.getAllSubmodules(execution_path=self.workspace_dir)
            activeSubprojects = git.getActiveSubmodules(execution_path=self.workspace_dir)

        if projectType == "nested subproject":
            config = config_parser_global.grapeConfig()
            allSubprojectNames = config.getAllNestedSubprojects()
            allSubprojects = []
            for project in allSubprojectNames:
                allSubprojects.append(config.get(f"nested-{project}", "prefix"))
            activeSubprojects = config_parser_user.getAllActiveNestedSubprojectPrefixes(workspaceDir=self.workspace_dir)

        toplevelDirs = {}
        toplevelActiveDirs = {}
        toplevelSubs = []
        for sub in allSubprojects:
            # we are taking advantage of the fact that branchPrefixes are the same as directory prefixes for local
            # top-level dirs.
            prefix = git.branchPrefix(sub)
            if sub != prefix:
                toplevelDirs[prefix] = []
                toplevelActiveDirs[prefix] = []
        for sub in allSubprojects:
            prefix = git.branchPrefix(sub)
            if sub != prefix:
                toplevelDirs[prefix].append(sub)
            else:
                toplevelSubs.append(sub)
        for sub in activeSubprojects:
            prefix = git.branchPrefix(sub)
            if sub != prefix:
                toplevelActiveDirs[prefix].append(sub)

        included = {}

        if self.uvManager:
            self.uvManager.createFrame(projectType)

        for directory, subprojects in sorted(toplevelDirs.items()):

            activeDir = toplevelActiveDirs[directory]
            if len(activeDir) == 0:
                defaultValue = "none"
            elif set(activeDir) == set(subprojects):
                defaultValue = "all"
            else:
                defaultValue = "some"

            if self.uvManager:
                opt = "s"
                self.uvManager.createSection(directory = directory, size = len(subprojects))
            else:
                opt = utility.userInput(f"Would you like all, some, or none of the {projectType}s in {directory}?",
                                        default=defaultValue)

            if opt is False:
                for subproject in subprojects:
                    included[subproject] = False
            elif opt is True:
                for subproject in subprojects:
                    included[subproject] = True
            elif opt.lower()[0] == "a":
                for subproject in subprojects:
                    included[subproject] = True
            elif opt.lower()[0] == "n":
                for subproject in subprojects:
                    included[subproject] = False
            elif opt.lower()[0] == "s":
                for subproject in sorted(subprojects, key=lambda v: (v.upper(), v[0].islower())):
                    if self.uvManager:
                        # Set the default value for the gui
                        subIsActive = subproject in activeSubprojects
                        included[subproject] = subIsActive
                        # subproject always uses "/" even on Windows
                        bareSubproject = subproject.partition(directory + "/")[2]
                        self.uvManager.createEntry(directory, bareSubproject, subIsActive)
                    else:
                        included[subproject] = utility.userInput(f"Would you like {projectType} {subproject}? [y/n]",
                                                                 'y' if (subproject in activeSubprojects) else 'n')
        if self.uvManager and toplevelSubs:
            self.uvManager.createSection(size = len(toplevelSubs))
        for subproject in sorted(toplevelSubs, key=lambda v: (v.upper(), v[0].islower())):
            if self.uvManager:
                # Set the default value for the gui
                subIsActive = subproject in activeSubprojects
                included[subproject] = subIsActive
                self.uvManager.createEntry("", subproject, subIsActive)
            else:
                included[subproject] = utility.userInput(f"Would you like {projectType} {subproject}? [y/n]",
                                                         'y' if (subproject in activeSubprojects) else 'n')
        return included

    def defineActiveNestedSubprojects(self):
        """
        Queries the user for the nested subprojects they would like to activate.

        """
        return self.defineActiveSubprojects(projectType="nested subproject")


    def verifySHAList(self, sha_dict):
        active_nested_subprojects = config_parser_user.getAllActiveNestedSubprojectPrefixes(workspaceDir=self.workspace_dir)
        config = config_parser_global.grapeConfig()
        CISubprojects = config.get("workspace","CIRepos").split(' ')
        valid = True
        for sub in CISubprojects:
            our_sha = git.SHA(execution_path=os.path.join(self.workspace_dir,sub))
            if sha_dict[sub] == our_sha:
                logging.info(f"subproject {sub} matches versions ({sha_dict[sub]})")
            else:
                valid = False
                logging.info(f"subproject {sub} at {our_sha}, expected at {sha_dict[sub]}")
                break
        return valid

    def getBranchChangedArgs(self, args):
        branchChangedArg = args["--branchChanged"]
        if branchChangedArg.endswith('~'):
            branchChanged = branchChangedArg[:-1]
            checkSubmoduleHistory = True
        else:
            branchChanged = branchChangedArg
            checkSubmoduleHistory = False
        public = config_parser_workspace.GrapeConfigParserWorkspace(self.workspace_dir).getPublicBranchFor(branchChanged)
        tagPrefix= None

        if branchChangedArg.endswith('~'):
            config = config_parser_global.grapeConfig()
            slotMappings = config.getMapping(self.SECTION_VERSIONING, "branchSlotMappings")
            slots = int(slotMappings[public])
            if slots > 1:
               prefix = config.get(self.SECTION_VERSIONING, "prefix")
               git.fetch("origin", f"--force --tags {public}", execution_path=self.workspace_dir)
               branchTags = git.describe(f"origin/{public} --match={prefix}*", execution_path=self.workspace_dir).split('.')
               tagPrefix = '.'.join(branchTags[:slots-1]) + '.'

        return (branchChanged, public, tagPrefix, checkSubmoduleHistory)

    # Return true if the subproject at url includes the branch (and it differs from public
    # if checkChanged is set).
    # If tagPrefix is provides, tags matching that pattern are considered as part of the
    # history of public (so if the branch matches the tag it is not considered different).
    @staticmethod
    def branchFilter(branch, subprojectPrefix, url, workspace_dir, subprojectPrefixList, checkChanged = False, public = None, tagPrefix = None, checkSubmoduleHistory = None):
        # If the branch exists locally, check there first (this will only detect if the branch exists and/or is changed,
        # not that it is unchanged).
        if subprojectPrefix in subprojectPrefixList:
           subpath = os.path.join(workspace_dir,subprojectPrefix)
           # subprojectPrefixList should filter by the active subprojects, but for nested subprojects some of the
           # "active" subprojects may not exist in a clean workspace.
           if os.path.exists(subpath):
              if git.hasBranch(branch, execution_path=subpath):
                 if checkChanged:
                     if not git.branchUpToDateWith(public, branch, execution_path=os.path.join(workspace_dir,subprojectPrefix)):
                         return True
                 else:
                     return True

        # Otherwise, look up from the remote
        branchHead = f"refs/heads/{branch}"
        lsRemoteFlags = "--heads"
        refs = branchHead
        if public:
            refs = f"{refs} refs/heads/{public}"
        if tagPrefix:
            lsRemoteFlags = lsRemoteFlags + " --tags"
            refs = f"{refs} refs/tags/{tagPrefix}*"
        remotes = git.lsRemote(f"{lsRemoteFlags} {git.parseSubprojectRemoteURL(url, execution_path=workspace_dir)} {refs}", execution_path=workspace_dir)

        branchSHA = None
        publicSHA = None
        tagSHA = []
        
        for entry in remotes.splitlines():
            if entry:
                SHA_and_ref = entry.split()
                if SHA_and_ref[1] == branchHead:
                    branchSHA = SHA_and_ref[0]
                elif public and SHA_and_ref[1] == f"refs/heads/{public}":
                    publicSHA = SHA_and_ref[0]
                elif tagPrefix and SHA_and_ref[1].startswith(f"refs/tags/{tagPrefix}"):
                    tagSHA.append(SHA_and_ref[0])

        if checkChanged:
           changed = branchSHA and branchSHA != publicSHA and (not tagSHA or branchSHA not in tagSHA)
           # Only check the submodule history if the submodule appears to be changed
           if changed and checkSubmoduleHistory:
               toppublic = config_parser_workspace.GrapeConfigParserWorkspace(workspace_dir).getPublicBranchFor(branch)
               # Get the SHAs in the outer repo corresponding to gitlink commits in the public branch
               revListCmd = f"rev-list origin/{toppublic} {subprojectPrefix}"
               gitLinkCommits = git.gitcmd(revListCmd, f"Could not run '{revListCmd}'", execution_path=workspace_dir)
               first = True
               for outerSHA in gitLinkCommits.splitlines():
                  # Skip first SHA in the history, as the gitlink may have been merged
                  # in before the branch is merged in the submodule.
                  if first:
                     first = False
                     continue

                  # Retrieve the gitlink metadata:
                  # [mode] [type] [SHA] [path]
                  lsTreeCmd = f"ls-tree {outerSHA} {subprojectPrefix}"
                  gitLinkInfo = git.gitcmd(lsTreeCmd, f"Could not run '{lsTreeCmd}'", execution_path=workspace_dir)
                  gitLinkEntries = gitLinkInfo.split()
                  if len(gitLinkEntries) > 1:
                     SHA = gitLinkEntries[2]
                     # If the SHA is otherwise in the gitlink history, consider the branch unchanged.
                     if SHA == branchSHA:
                        changed = False
                        break
                  else:
                     logging.warning(f"WARNING: invalid gitlink entry for {subprojectPrefix} at {outerSHA} : {gitLinkInfo}")
           return changed
        else:
           return branchSHA != None

    @staticmethod
    def force_rm(func, path, excinfo):
        os.chmod(path, stat.S_IWRITE)
        func(path)

    def rmNestedSubproject(self, subproject, args):
        subprojectdir = os.path.join(self.workspace_dir, subproject)
        proceed = args["-F"] or \
                  utility.userInput(f"About to delete all contents in {subproject}. " +
                                    "Any uncommitted changes, committed changes that have " +
                                    "not been pushed, or ignored files will be lost.  Proceed?" +
                                    " (use -F to force removal without this prompt)", 'n')
        if proceed:
            logging.info(f"removing {subproject}...")
            shutil.rmtree(subprojectdir, onerror=self.force_rm)
            return True
        return False

    @log_wrapper
    def execute(self, args):
        branch = args["--branchName"] if args["--branchName"] else git.currentBranch(execution_path=self.workspace_dir)
        if branch == "HEAD":
           logging.error("grape uv cannot check out HEAD, you must specify --branchName or get out of the detached HEAD state!")
           return False
        hasSubmodules = len(git.getAllSubmodules(execution_path=self.workspace_dir)) > 0 and not args["--skipSubmodules"]
        allSubmodules = git.getAllSubmodules(execution_path=self.workspace_dir)
        if hasSubmodules:
           url_map = git.getAllSubmoduleURLMap(execution_path=self.workspace_dir)

        if args["--checkRemoteSubmodules"]:
            submodulesConsistent = True
            if args["--allSubmodules"]:
               checkedSubmodules = allSubmodules
            else:
               checkedSubmodules = git.getActiveSubmodules(execution_path=self.workspace_dir)

            for submodule in checkedSubmodules:
               remote_url = git.parseSubprojectRemoteURL(url_map[submodule], execution_path=self.workspace_dir)
               subpublicmapping = config_parser_workspace.GrapeConfigParserWorkspace(self.workspace_dir).getMapping(Option.SECTION_WORKSPACE, "submodulepublicmappings")
               subbranch = subpublicmapping[branch] if branch in subpublicmapping else branch
               remotes = git.lsRemote(f"--heads {remote_url} refs/heads/{subbranch}", execution_path=self.workspace_dir).splitlines()
               # The git remote command output may include X11 forwarding output, so only consider lines with refs/heads
               for remote in remotes:
                  if "refs/heads" in remote:
                     # Get the SHAs for gitlink of each submodule
                     SHA = git.SHA(f"origin/{branch}:{submodule}", execution_path=self.workspace_dir)
                     if SHA not in remote:
                        logging.info(f"Branch {subbranch} in submodule {submodule} at {remote.split()[0]}, expected {SHA}")
                        submodulesConsistent = False
            return submodulesConsistent

        config = config_parser_global.grapeConfig()
        if args["--gui"] and TkinterImportError:
            logging.error("grape uv --gui requires Tkinter.\n  The following error was raised during the import:\n\n%s\n" % TkinterImportError)
            return True

        if args["--verifySHAList"]:
            with open(os.path.join(self.workspace_dir,"GRAPE_PROJECT_SHA.json"),'r') as f:
                sha_dict = json.load(f)
            return self.verifySHAList(sha_dict)

        sync = args["--sync"].lower().strip() in ["true", "yes"]
        args["--sync"] = sync
        base = git.baseDir(execution_path=self.workspace_dir)
        if base == "":
            return False
        includedSubmodules = {}
        includedNestedSubprojectPrefixes = {}

        allNestedSubprojects = config.getAllNestedSubprojects()

        nonInteractive = args["--allSubmodules"] or args["--noSubmodules"] or args["--allNestedSubprojects"] or args["--noNestedSubprojects"] or args["--branchFilter"] or args["--branchChanged"] or args["--add"] or args["--rm"] or args["--ensureCIReposPresent"]

        if args["--gui"] and nonInteractive:
            logging.error("grape uv --gui cannot be used in non-interactive mode")
            return True

        addedSubmodules = []
        addedNestedSubprojects = []
        addedProjects = args["--add"]
        if args["--ensureCIReposPresent"]:
            CIRepos = config.get("workspace","CIRepos").split(' ')
            addedProjects = addedProjects + CIRepos
        notFound = []

        for proj in addedProjects:
            if proj in allSubmodules:
                addedSubmodules.append(proj)
            elif proj in allNestedSubprojects:
                addedNestedSubprojects.append(proj)
            else:
                notFound.append(proj)

        rmSubmodules = []
        rmNestedSubprojects = []
        rmProjects = args["--rm"]

        for proj in rmProjects:
            if proj in allSubmodules:
                rmSubmodules.append(proj)
            elif proj in allNestedSubprojects:
                rmNestedSubprojects.append(proj)
            else:
                notFound.append(proj)

        if notFound:
            logging.info(f"\"{','.join(notFound)}\" not found in submodules {','.join(allSubmodules)} \nor\n nested subprojects {','.join(allNestedSubprojects)}")
            return False

        delayedMessages = []

        if not args["--checkSubprojects"]:
            root = None
            if args["--gui"]:
                root = Tk.Tk()
                root.title("GRAPE uv - select active subprojects")
                self.uvManager = UVManager(master=root)

            # get submodules to update
            if hasSubmodules:
                if args["--branchFilter"]:
                    branchFilter = lambda x : self.branchFilter(args['--branchFilter'], x, url_map[x], self.workspace_dir, git.getActiveSubmodules(execution_path=self.workspace_dir))
                elif args["--branchChanged"]:
                    (branchChanged, public, tagPrefix, checkSubmoduleHistory) = self.getBranchChangedArgs(args)
                    subpublic = config_parser_workspace.GrapeConfigParserWorkspace(self.workspace_dir).getMapping(Option.SECTION_WORKSPACE, "submodulepublicmappings")[public]
                    branchFilter = lambda x : self.branchFilter(branchChanged, x, url_map[x], self.workspace_dir, git.getActiveSubmodules(execution_path=self.workspace_dir), checkChanged=True, public=subpublic, checkSubmoduleHistory=checkSubmoduleHistory)
                else:
                    branchFilter = lambda x : True

                if args["--allSubmodules"]:
                    includedSubmodules = {sub:branchFilter(sub) for sub in allSubmodules}
                elif args["--noSubmodules"]:
                    includedSubmodules = {sub:False for sub in git.getActiveSubmodules(execution_path=self.workspace_dir)}
                elif nonInteractive:
                    includedSubmodules = {sub:branchFilter(sub) for sub in git.getActiveSubmodules(execution_path=self.workspace_dir)}
                else:
                    includedSubmodules = self.defineActiveSubprojects()

                if args["--add"] or args["--rm"] or args["--ensureCIReposPresent"]:
                    includedSubmodules.update({sub:True for sub in addedSubmodules})
                    includedSubmodules.update({sub:False for sub in rmSubmodules})

            # get subprojects to update
            if not args["--skipNestedSubprojects"]:
                nestedPrefixLookup = lambda x : config.get(f"nested-{x}", "prefix")

                if args["--branchFilter"]:
                    branchFilter = lambda x : self.branchFilter(args['--branchFilter'], config.get(f"nested-{x}", "prefix"), config.get(f"nested-{x}", "url"), self.workspace_dir, config_parser_user.getAllActiveNestedSubprojectPrefixes(workspaceDir=self.workspace_dir))
                elif args["--branchChanged"]:
                    (branchChanged, public, tagPrefix, checkSubmoduleHistory) = self.getBranchChangedArgs(args)
                    branchFilter = lambda x : self.branchFilter(branchChanged, config.get(f"nested-{x}", "prefix"), config.get(f"nested-{x}", "url"), self.workspace_dir, config_parser_user.getAllActiveNestedSubprojectPrefixes(workspaceDir=self.workspace_dir), checkChanged = True, public=public, tagPrefix=tagPrefix)
                else:
                    branchFilter = lambda x : True

                if args["--allNestedSubprojects"]:
                    includedNestedSubprojectPrefixes = {nestedPrefixLookup(sub):branchFilter(sub) for sub in allNestedSubprojects}
                elif args["--noNestedSubprojects"]:
                    includedNestedSubprojectPrefixes = {nestedPrefixLookup(sub):False for sub in config_parser_user.getAllActiveNestedSubprojects(workspaceDir=self.workspace_dir)}
                elif nonInteractive:
                    includedNestedSubprojectPrefixes = {nestedPrefixLookup(sub):branchFilter(sub) for sub in config_parser_user.getAllActiveNestedSubprojects(workspaceDir=self.workspace_dir)}
                else:
                    includedNestedSubprojectPrefixes = self.defineActiveNestedSubprojects()

                if args["--add"] or args["--rm"]:
                    includedNestedSubprojectPrefixes.update({nestedPrefixLookup(sub):True for sub in addedNestedSubprojects})
                    includedNestedSubprojectPrefixes.update({nestedPrefixLookup(sub):False for sub in rmNestedSubprojects})

            if root:
                self.uvManager.finalize()
                root.mainloop()
                if self.uvManager.saved is False:
                    logging.info("Not changing working view.")
                    return False
                # If --all/--add/--rm is used, only consider the
                # command line for the included subprojects.
                if self.uvManager.includedSubmodules is None:
                    logging.info("Submodule changes from GUI ignored")
                else:
                    includedSubmodules = self.uvManager.includedSubmodules
                if self.uvManager.includedNestedSubprojects is None:
                    logging.info("Nested subproject changes from GUI ignored")
                else:
                    includedNestedSubprojectPrefixes = self.uvManager.includedNestedSubprojects
                try:
                    root.destroy()
                except:
                    pass

            remoteProtocolSubmodules = []
            if args["--updateRemoteProtocol"]:
                remoteProtocol = git.remote("get-url origin", execution_path=self.workspace_dir).split(":")[0]

            if hasSubmodules:
                initStr = ""
                deinitStr = ""
                rmCachedStr = ""
                resetStr = ""
                for submodule, nowActive in includedSubmodules.items():
                    if nowActive:
                        initStr += f' {submodule}'
                        if args["--updateRemoteProtocol"]:
                            subRemoteProtocol = git.remote("get-url origin", execution_path=os.path.join(self.workspace_dir,submodule)).split(":")[0]
                            if subRemoteProtocol != remoteProtocol:
                               logging.info(f"Remote protocol for submodule {submodule} is {subRemoteProtocol}://, reinitializing with {remoteProtocol}://...")
                               remoteProtocolSubmodules.append(submodule)
                               deinitStr += f' {submodule}'
                               rmCachedStr += f' {submodule}'
                               resetStr += f' {submodule}'
                    else:
                        deinitStr += f' {submodule}'
                        rmCachedStr += f' {submodule}'
                        resetStr += f' {submodule}'
                if args["-f"] and deinitStr:
                    deinitStr = "-f"+deinitStr

                logging.info("Configuring submodules...")
                if not remoteProtocolSubmodules:
                    logging.info("Initializing submodules...")
                    git.submodule(f"init {initStr.strip()}", execution_path=self.workspace_dir)

                if deinitStr:
                    logging.info(f"Deiniting submodules that were not requested... ({deinitStr})")
                    done = False
                    while not done:
                        try:
                            git.submodule(f"deinit {deinitStr.strip()}",
                                          execution_path=self.workspace_dir)
                            done = True
                        except grape_errors.GrapeGitError as e:
                            if "the following file has local modifications" in e.gitOutput.lower():
                                logging.error(e.gitOutput)
                                logging.error(
                                    "A submodule that you wanted to remove " +
                                    "has local modifications. " +
                                    "Use grape uv -f to force removal.")
                                if remoteProtocolSubmodules:
                                    logging.error(f"Remote protocol not changed for {' '.join(remoteProtocolSubmodules)}!")
                                return False
                            elif "use 'rm -rf' if you really want to remove it including all of its history" in e.gitOutput.lower():
                                if not args["-f"]:
                                    raise e
                                # it is safe to move the .git of the submodule to the .git/modules area of the workspace...
                                module = None
                                for l in e.gitOutput.lower().split('\n'):
                                    if "submodule work tree" in l and "contains a .git directory" in l:
                                        module = l.split("'")[1]
                                        break
                                if module:
                                    src = os.path.join(module, ".git")
                                    dest =  os.path.join(self.workspace_dir, ".git", "modules", module)
                                    logging.info(f"Moving {src} to {dest}")
                                    shutil.move(src, dest)
                                else:
                                    raise e
                            else:
                                raise e
                    git.rm(f"--cached {rmCachedStr}",
                           execution_path=self.workspace_dir)
                    git.reset(f" {resetStr}", execution_path=self.workspace_dir)

                if remoteProtocolSubmodules:
                   for submodule in remoteProtocolSubmodules:
                       shutil.rmtree(os.path.join(self.workspace_dir, ".git", "modules", submodule), onerror=self.force_rm)

                   logging.info("Initializing submodules after updating remote protocols...")
                   git.submodule(f"init {initStr.strip()}", execution_path=self.workspace_dir)

                if initStr:
                    logging.info(f"Updating active submodules...({initStr})")
                    git.submodule("update", execution_path=self.workspace_dir)

            # handle nested subprojects
            if not args["--skipNestedSubprojects"]:
                reverseLookupByPrefix = {nestedPrefixLookup(sub) : sub for sub in allNestedSubprojects}
                userConfig = config_parser_user.GrapeConfigParserUser(workspace_dir=self.workspace_dir, read_global=False)
                updatedActiveList = []
                toActivate_args = []
                toRemove = []
                for subproject, nowActive in includedNestedSubprojectPrefixes.items():
                    subprojectName = reverseLookupByPrefix[subproject]
                    section = f"nested-{subprojectName}"
                    userConfig.ensureSection(section)
                    subproject = git.gitPathToOsPath(subproject)
                    previouslyActive = userConfig.getboolean(section, "active")
                    previouslyActive = previouslyActive and os.path.exists(os.path.join(self.workspace_dir, subproject, ".git"))
                    userConfig.set(section, "active", "True" if previouslyActive else "False")
                    if nowActive and previouslyActive:
                        if args["--updateRemoteProtocol"]:
                            subRemoteProtocol = git.remote("get-url origin", execution_path=os.path.join(self.workspace_dir,subproject)).split(":")[0]
                            if subRemoteProtocol != remoteProtocol:
                                logging.info(f"Remote protocol for nested subproject {subproject} is {subRemoteProtocol}://, deleting and recloning with {remoteProtocol}://...")
                                if self.rmNestedSubproject(subproject, args):
                                    toActivate_args.append((subprojectName,'', {"userConfig" : userConfig, "subprojectName":subprojectName}))
                                    section = f"nested-{subprojectName}"
                                    userConfig.ensureSection(section)
                                    userConfig.set(section, "active", "False")
                                    config_parser_global.writeConfig(userConfig, os.path.join(self.workspace_dir, ".git", ".grapeuserconfig"))
                                else:
                                    delayedMessages.append(f"Remote protocol for nested subproject {subproject} was not changed!")

                        updatedActiveList.append(subprojectName)

                    if nowActive and not previouslyActive:
                        toActivate_args.append((subprojectName,'', {"userConfig" : userConfig, "subprojectName":subprojectName}))

                        updatedActiveList.append(subprojectName)

                    if not nowActive and not previouslyActive:
                        pass
                    if not nowActive and previouslyActive:
                        #remove the subproject
                        subprojectdir = os.path.join(self.workspace_dir, subproject)
                        self.rmNestedSubproject(subproject, args)

                # activate nested subprojects in parallel
                activate_project_launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(activateSubproject,
                                                                                             listOfRepoBranchArgTuples=toActivate_args,
                                                                                             workspace_dir=self.workspace_dir)
                retvals = activate_project_launcher.launchFromWorkspaceDir(handleMRE=handleActivateSubprojectMRE)
                if False in retvals:
                    for msg in delayedMessages:
                        logging.info(msg)
                    return False
                                                                                                 
                    
                userConfig.setActiveNestedSubprojects(updatedActiveList)
                config_parser_global.writeConfig(userConfig, os.path.join(self.workspace_dir, ".git", ".grapeuserconfig"))

        checkoutArgs = "-b" if args["-b"] else ""

        safeSwitchWorkspaceToBranch(
            branch, checkoutArgs, sync,
            runInOuter=not args["--skipTopLevel"],
            skipSubmodules=args["--skipSubmodules"],
            runInSubprojects=not args["--skipNestedSubprojects"],
            skipBranchCreation=args["--skipBranchCreation"],
            skipSubmoduleSwitch=args["--skipSubmoduleSwitch"],
            workspace_dir=self.workspace_dir)


        if args["--generateSHAList"]:
            nested_subprojects = config_parser_user.getAllActiveNestedSubprojectPrefixes(workspaceDir=self.workspace_dir)
            sha_dict = {}
            for sub in nested_subprojects:
                sha_dict[sub] = git.SHA(execution_path=os.path.join(self.workspace_dir,sub))
            # write dict in a pickle file
            with open(os.path.join(self.workspace_dir,"GRAPE_PROJECT_SHA.json"),'w') as f:
                json.dump(sha_dict, f)


        if args["--spackEnv"]:
            # create a Spack Environmnet for a collection of submodules
            # to develop
            self.spackDevelopEnvironment()


        for msg in delayedMessages:
            logging.info(msg)
        return True

    # Spack Develop Environment Option call a script to gather
    # name and versions of currently checkedout libraries
    # to make the correct spack develop or undevelop calls
    def spackDevelopEnvironment(self):
        """
        User needs to be in an active Spack environmnet.
        spack env activate -p <path/to/file>
        grape uv --spackEnv

        """
        activeSubmodules = git.getActiveSubmodules(execution_path=self.workspace_dir)
        # read list of spack projects from configuration
        config = config_parser_global.grapeConfig()
        spack_projects = config.get("spackProjects", "submodules").split()
        script = config.get("spackProjects", "script")
        logging.info(f"Available Spack projects = {spack_projects}")

        # passing Spack Projects from .grapeconfig [spackProjects] submodules
        # to the spack script to get versions and path of libraries
        develop_libs = []
        undevelop_libs = []

        if script:
            for submodule in spack_projects:
                if submodule in activeSubmodules:
                    develop_libs.append(submodule)
                else:
                    undevelop_libs.append(submodule)
            # cmd f string to built up by develop and undevelop libs to do a single call to the script
            cmd = f"python3 {script}"
            # if there are libs to develop or undevelop then they will get concatenated to cmd
            if develop_libs:
                cmd += f" --libs {','.join(develop_libs)}"
            if undevelop_libs:
                cmd += f" --undevelop {','.join(undevelop_libs)}"

            vine_subprocess.executeSubProcess(cmd, self.workspace_dir)
            logging.info(f"Spack develop environment at {self.workspace_dir} has been updated")


    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_WORKSPACE)
        config.ensureSection(self.SECTION_SPACK_PROJECTS)
        config.set(self.SECTION_WORKSPACE, "submodulepublicmappings", "?:master")
        config.set(self.SECTION_WORKSPACE, "CIRepos", " ")
        config.set(self.SECTION_SPACK_PROJECTS, "submodules", " ")
        config.set(self.SECTION_SPACK_PROJECTS, "script", " ")

def activateSubproject(repo='', branch='develop', args={}, *, workspace_dir):
    userConfig = args["userConfig"]
    subprojectName = args["subprojectName"]
    logging.info(f"Activating Nested Subproject {subprojectName}")
    if not addSubproject.AddSubproject.activateNestedSubproject(subprojectName, userConfig, workspace_dir):
        logging.info(f"Can't activate {subprojectName}. Exiting...")
        return False
    logging.info(f"Nested Subproject {subprojectName} activated.")
    return True

def handleActivateSubprojectMRE(mre):
    for e1 in mre.exceptions():
        raise e1

    


def ensureLocalUpToDateWithRemote(repo='', branch='master', args=[], *, workspace_dir):
    skipSubmoduleSwitch = args[0]
    logging.info(f"Ensuring local branch {branch} in {repo} is up to date with origin")
    # attempt to fetch the requested branch
    try:
        git.fetch("origin", f"{branch}:{branch}", execution_path=repo)
    except grape_errors.GrapeGitError as e:
        if "refusing to fetch into current branch" in e.gitOutput.lower():
            try:
                git.pull(f"origin {branch}", execution_path=repo)
            except grape_errors.GrapeGitError as e:
                logging.error(e.gitOutput)
                raise e
        else:
            logging.info(f"Fetch to update {branch} in {repo} failed : {e.gitOutput}\n\tContinuing...")
        pass

    # Get the public branch
    public = config_parser_workspace.GrapeConfigParserWorkspace(workspace_dir).getPublicBranchFor(branch)
    # figure out if this is a submodule
    relpath = os.path.relpath(repo, workspace_dir)
    # if this is a submodule, get the appropriate public mapping
    isSubmodule = utility.win_path_to_linux_path(relpath) in git.getAllSubmoduleURLMap(execution_path=workspace_dir).keys()
    if isSubmodule:
        public = config_parser_workspace.GrapeConfigParserWorkspace(workspace_dir).getMapping(Option.SECTION_WORKSPACE, "submodulepublicmappings")[public]

    if branch != public:
        git.fetch("origin", f"--force {public}:{public}", execution_path=repo)

    try:
        if git.currentBranch(execution_path=repo) == branch:
           return
    except grape_errors.GrapeGitError:
        # In certain cases, like an interrupted clone, HEAD may not be defined,
        # so currentBranch() may raise an exception. Ignore that exception, since
        # it indicates that we are not currently on the correct branch (so we don't
        # want an early return).
        pass

    if not git.hasBranch(branch, execution_path=repo):
        # switch to corresponding public branch if the branch does not exist
        if isSubmodule:
            if skipSubmoduleSwitch:
               logging.info(f"Branch {branch} does not exist in {repo}, skipping switch to public branch")
               return
        logging.info(f"Branch {branch} does not exist in {repo}, switching to {public} and detaching")
        git.checkout(public, execution_path=repo)
        git.pull(f"origin {public}", execution_path=repo)
        git.checkout("--detach HEAD", execution_path=repo)

def cleanupPush(repo='', branch='', args='none', *, execution_path):
    logging.info(f"Attempting push of local {branch} in {repo}")
    git.push(f"origin {branch}", execution_path=repo)


def handleCleanupPushMRE(mre):
    for e, repo, branch in zip(mre.exceptions(), mre.repos(), mre.branches()):
        try:
            raise e
        except grape_errors.GrapeGitError as e2:
            logging.error(f"Local and remote versions of {branch} may have diverged in {repo}")
            logging.error(f"{e2.gitOutput}")
            logging.error("Use grape pull to merge the remote version into the local version.")

def handleEnsureLocalUpToDateMRE(mre):
    _pushBranch = False
    _skipPush = False
    cleanupPushArgs = []
    for e1, repo, branch in zip(mre.exceptions(), mre.repos(), mre.branches()):
        try:
            raise e1
        except grape_errors.GrapeGitError as e:
            if ("[rejected]" in e.gitOutput.lower() and "(non-fast-forward)" in e.gitOutput.lower()) or e.could_not_find_remote_ref():
                if e.could_not_find_remote_ref():
                    if not _pushBranch:
                        logging.info(f"No remote reference to {branch} in {repo}'s origin. You may want to push this branch.")
                else:
                    logging.info(f"Fetch of {branch} rejected as non-fast-forward in repo {repo}")
                pushBranch = _pushBranch
                if _skipPush:
                    pushBranch = False
                elif not pushBranch:
                    pushBranch =  utility.userInput("Would you like to push your local branch? \n"
                                                    "(select 'a' to say yes for (a)ll subprojects, 's' to (s)kip push for all subprojects)"
                                                    "\n(y,n,a,s)", 'y')

                if str(pushBranch).lower()[0] == 'a':
                    _pushBranch = True
                    pushBranch = True
                if str(pushBranch).lower()[0] == 's':
                    _skipPush = True
                    pushBranch = False
                if pushBranch:

                    cleanupPushArgs.append((repo, branch, None))
                else:
                    logging.info(f"Skipping push of local {branch} in {repo}")

            elif e.commError:
                logging.error(f"Could not update {branch} from origin due" +
                              " to a connectivity issue. Checking out most" +
                              " recent\nlocal version. ")
            else:
                raise(e)

    # do another MRC launch to do any follow up pushes that were requested.
    launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
        cleanupPush, listOfRepoBranchArgTuples=cleanupPushArgs,
        workspace_dir=mre.workspace_dir)
    launcher.launchFromWorkspaceDir(handleMRE=handleCleanupPushMRE)
    return

def safeSwitchWorkspaceToBranch(branch, checkoutArgs, sync, *, workspace_dir, runInOuter=True, skipSubmodules=False, runInSubprojects=True, skipBranchCreation=False, skipSubmoduleSwitch=False ):
    # Ensure local branches that you are about to check out are up to date with the remote
    if sync:
        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
            ensureLocalUpToDateWithRemote, branch=branch,
            runInOuter=runInOuter, skipSubmodules=skipSubmodules, runInSubprojects=runInSubprojects,
            globalArgs=[skipSubmoduleSwitch], workspace_dir=workspace_dir)
        launcher.launchFromWorkspaceDir(handleMRE=handleEnsureLocalUpToDateMRE)
    # Do a checkout
    # Pass False instead of sync since if sync is True ensureLocalUpToDateWithRemote will have already performed the fetch
    launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
        checkout.handledCheckout, branch=branch,
        runInOuter=runInOuter, skipSubmodules=skipSubmodules, runInSubprojects=runInSubprojects,
        globalArgs=[checkoutArgs, False], workspace_dir=workspace_dir)
    if skipBranchCreation:
       launcher.launchFromWorkspaceDir(handleMRE=checkout.handleCheckoutSkipBranchCreationMRE)
    else:
       launcher.launchFromWorkspaceDir(handleMRE=checkout.handleCheckoutMRE)


# Class for selecting subprojects in a workspace
class UVManager:
    def __init__(self, master, **kwargs):
        height = kwargs.get('height', 0)
        width  = kwargs.get('width', 0)

        # Saved lists of active subprojects (None if not saved)
        # subproject_join is used instead of os.path.join() so that the subproject
        # names use the Linux slash convention used in the .grapeconfig.
        self.includedSubmodules = None
        self.includedNestedSubprojects = None
        self.saved = False

        self.master = master
        self.currentProjectIndex = None

        # 0 is submodules
        # 1 is nested subprojects
        self.activeSets = [ None, None ]
        self.inactiveSets = [ None, None ]
        self.originalActiveSets = [ None, None ]

        self.currentFrame = None
        self.currentActiveList = None
        self.currentInactiveList = None

        # Colors
        self.fginit     = kwargs.get('fginit', 'black')
        self.bginit     = kwargs.get('bginit', 'gray')
        self.fgselected = kwargs.get('fgselected', 'black')
        self.bgselected = kwargs.get('bgselected', 'goldenrod')
        self.fgchanged   = kwargs.get('fgchanged', 'blue')

        self.active = []
        self.inactive = []
        # offset so first call to createFrame starts at 0
        self.currentColumn = -2
        self.currentRow = 0

        # Main resizable window
        self.main = Tk.PanedWindow(master, height=height, width=width, sashwidth=4)
        controlpanel = Tk.Frame()
        savebutton = Tk.Button(controlpanel, text="Save and Update", command = self.saveChanges)
        savebutton.grid(row=0, column=0)
        cancelbutton = Tk.Button(controlpanel, text="Cancel", command = self.master.destroy)
        cancelbutton.grid(row=0, column=1)
        controlpanel.grid(row=0, column=0)

    # Return Linux formatted joined path for subproject
    @staticmethod
    def subproject_join(directory, subproject):
        if directory:
            return '/'.join([directory, subproject])
        else:
            return subproject

    # Save changes and exit
    def saveChanges(self):
        if self.activeSets[0] is not None:
            self.saved = True
            self.includedSubmodules = {}
            for sub in self.activeSets[0]:
                self.includedSubmodules[sub] = True
            for sub in self.inactiveSets[0]:
                self.includedSubmodules[sub] = False
        if self.activeSets[1] is not None:
            self.saved = True
            self.includedNestedSubprojects = {}
            for sub in self.activeSets[1]:
                self.includedNestedSubprojects[sub] = True
            for sub in self.inactiveSets[1]:
                self.includedNestedSubprojects[sub] = False
        self.master.destroy()

    # Save the original set of active subprojects and sort the last section
    def finalize(self):
        # sort the last section
        self.resortList(self.currentActiveList)
        self.resortList(self.currentInactiveList)

        # save the original state
        for i in [0, 1]:
            self.originalActiveSets[i] = set()
            if self.activeSets[i]:
               for sub in self.activeSets[i]:
                   self.originalActiveSets[i].add(sub)


    # Start a new frame for different project type
    def createFrame(self, projectType):
        self.currentRow = 2
        self.currentColumn = self.currentColumn + 2
        frame = Tk.Frame()
        label = Tk.Label(frame, text=f"Select {projectType}s")
        label.grid()
        self.master.grid_rowconfigure(self.currentRow, weight=1, minsize=70)
        self.master.grid_columnconfigure(self.currentColumn, weight=1)
        self.master.grid_columnconfigure(self.currentColumn+1, weight=1)
        frame.grid(row=1, column=self.currentColumn, columnspan=2, sticky="nsew")
        if projectType == "submodule":
            self.currentProjectIndex = 0
        elif projectType == "nested subproject":
            self.currentProjectIndex = 1

    # Start a new section for a different directory
    def createSection(self, directory = "", size = 1):
        directory_name = "top level" if directory == "" else directory
        
        # sort the previous section (if any)
        self.resortList(self.currentActiveList)
        self.resortList(self.currentInactiveList)

        height = min(size, 8)
        width = 30

        activepanel = Tk.Frame()
        activelabel = Tk.Label(activepanel, text=f"Active in {directory_name}")
        activescroll = Tk.Scrollbar(activepanel, width=10)
        activelist = Tk.Listbox(activepanel, background=self.bginit, foreground=self.fginit,
                                selectbackground=self.bgselected, selectforeground=self.fgselected,
                                yscrollcommand=activescroll.set, selectmode=Tk.SINGLE, height=height, width=width)
        activescroll.config(command=activelist.yview)
        activescroll.grid(row=2, column=0, sticky=Tk.N+Tk.S)
        activelabel.grid(row=0, column=0, columnspan=2)
        activelist.grid(row=2, column=1)
        activepanel.grid(row=self.currentRow, column=self.currentColumn)
        activepanel.grid_rowconfigure(self.currentRow, minsize=20)

        activepanel.grid_rowconfigure(2, weight=1)
        activepanel.grid_columnconfigure(1, weight=1)
        activelist.grid(row=2, column=1, sticky="nsew")
        activepanel.grid(row=self.currentRow, column=self.currentColumn, sticky="nsew")
        self.currentActiveList = activelist

        inactivepanel = Tk.Frame()
        inactivelabel = Tk.Label(inactivepanel, text=f"Inactive in {directory_name}")
        inactivescroll = Tk.Scrollbar(inactivepanel, width=10)
        inactivelist = Tk.Listbox(inactivepanel, background=self.bginit, foreground=self.fginit,
                                  selectbackground=self.bgselected, selectforeground=self.fgselected,
                                  yscrollcommand=inactivescroll.set, selectmode=Tk.SINGLE, height=height, width=width)
        inactivescroll.config(command=inactivelist.yview)
        inactivescroll.grid(row=2, column=0, sticky=Tk.N+Tk.S)
        inactivelabel.grid(row=0, column=0, columnspan=2)
        inactivepanel.grid_rowconfigure(2, weight=1)
        inactivepanel.grid_columnconfigure(1, weight=1)
        inactivelist.grid(row=2, column=1, sticky="nsew")
        inactivepanel.grid(row=self.currentRow, column=self.currentColumn+1, sticky="nsew")
        inactivepanel.grid_rowconfigure(self.currentRow, minsize=20)
        self.currentInactiveList = inactivelist

        self.currentRow = self.currentRow + 2

        index = self.currentProjectIndex
        activelist.bind("<Double-Button-1>", lambda e: self.deactivateProject(directory, activelist, inactivelist,
                                                                              self.activeSets[index], self.inactiveSets[index],
                                                                              self.originalActiveSets[index]))
        inactivelist.bind("<Double-Button-1>", lambda e: self.activateProject(directory, activelist, inactivelist,
                                                                              self.activeSets[index], self.inactiveSets[index],
                                                                              self.originalActiveSets[index]))

        activeall = Tk.Button(activepanel, text="activate all", borderwidth=0, foreground="darkblue",
                              command = lambda : self.activateAll(directory, activelist, inactivelist,
                                                                  self.activeSets[index], self.inactiveSets[index],
                                                                  self.originalActiveSets[index]))
        activeall.grid(row=1, column=0, columnspan=2)
        inactiveall = Tk.Button(inactivepanel, text="deactivate all", borderwidth=0, foreground="darkblue",
                                command = lambda : self.deactivateAll(directory, activelist, inactivelist,
                                                                      self.activeSets[index], self.inactiveSets[index],
                                                                      self.originalActiveSets[index]))
        inactiveall.grid(row=1, column=0, columnspan=2)


    # Create an entry for a subproject
    def createEntry(self, directory, subproject, isActive):
        if self.activeSets[self.currentProjectIndex] is None:
            self.activeSets[self.currentProjectIndex] = set()
        if self.inactiveSets[self.currentProjectIndex] is None:
            self.inactiveSets[self.currentProjectIndex] = set()

        if isActive:
            self.currentActiveList.insert(Tk.END, subproject)
            self.activeSets[self.currentProjectIndex].add(self.subproject_join(directory,subproject))
        else:
            self.currentInactiveList.insert(Tk.END, subproject)
            self.inactiveSets[self.currentProjectIndex].add(self.subproject_join(directory,subproject))

    # Activate selected project
    def activateProject(self, directory, activelist, inactivelist, activeset, inactiveset, originalactiveset):
        index = inactivelist.index(Tk.ACTIVE)
        entry = inactivelist.get(index)
        inactivelist.delete(index)
        inactiveset.remove(self.subproject_join(directory,entry))
        activelist.insert(Tk.END, entry)
        activeset.add(self.subproject_join(directory,entry))
        self.resortList(activelist, originalactiveset, self.fginit, self.fgchanged, directory)
        self.resortList(inactivelist, originalactiveset, self.fgchanged, self.fginit, directory)
        self.master.update()

    # Deactivate selected project
    def deactivateProject(self, directory, activelist, inactivelist, activeset, inactiveset, originalactiveset):
        index = activelist.index(Tk.ACTIVE)
        entry = activelist.get(index)
        activelist.delete(index)
        activeset.remove(self.subproject_join(directory,entry))
        inactivelist.insert(Tk.END, entry)
        inactiveset.add(self.subproject_join(directory,entry))
        self.resortList(activelist, originalactiveset, self.fginit, self.fgchanged, directory)
        self.resortList(inactivelist, originalactiveset, self.fgchanged, self.fginit, directory)
        self.master.update()

    # Activate all projects in the section
    def activateAll(self, directory, activelist, inactivelist, activeset, inactiveset, originalactiveset):
        entries = inactivelist.get(0, Tk.END)
        inactivelist.delete(0,Tk.END)
        for entry in entries:
            activelist.insert(Tk.END, entry)
            activeset.add(self.subproject_join(directory,entry))
            inactiveset.remove(self.subproject_join(directory,entry))
        self.resortList(activelist, originalactiveset, self.fginit, self.fgchanged, directory)
        self.resortList(inactivelist, originalactiveset, self.fgchanged, self.fginit, directory)
        self.master.update()

    # Deactivate all projects in the section
    def deactivateAll(self, directory, activelist, inactivelist, activeset, inactiveset, originalactiveset):
        entries = activelist.get(0, Tk.END)
        activelist.delete(0,Tk.END)
        for entry in entries:
            inactivelist.insert(Tk.END, entry)
            inactiveset.add(self.subproject_join(directory,entry))
            activeset.remove(self.subproject_join(directory,entry))
        self.resortList(activelist, originalactiveset, self.fginit, self.fgchanged, directory)
        self.resortList(inactivelist, originalactiveset, self.fgchanged, self.fginit, directory)
        self.master.update()

    # Resort and format the list boxes
    def resortList(self, listbox, originalset = None, inSetColor = None, notInSetColor = None, directory = ""):
        if listbox:
           entries = listbox.get(0, Tk.END)
           listbox.delete(0, Tk.END)
           for entry in sorted(entries):
               listbox.insert(Tk.END, entry)
               if originalset is not None:
                   if self.subproject_join(directory,entry) in originalset:
                       listbox.itemconfig(Tk.END, fg=inSetColor)
                   else:
                       listbox.itemconfig(Tk.END, fg=notInSetColor)
