import glob
import logging
import os
from vine import config_parser_base
from vine import config_parser_global
from vine import config_parser_workspace
from vine import grape_errors
from vine import grapeGit as git
from vine import multi_repo_cmd_launcher
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.option import Option
from vine.vine_logging import log_wrapper


# Create git bundle files for each repo
class Bundle(Option, WorkspaceDirHandler):

    """
    grape bundle uses the 'git bundle' feature to extract a subset of history into a git bundle file,
    which can then be sent over a sneakernet to a mirror of your grape project.
    The history range that is extracted is defined in the following way:
        start point:
            for each branch in <list> as defined by --branches, start at the commit tagged by
            <tagprefix>/<branch>.
        end point:
            the tip of each branch in <list> as defined by --branches.
    By default, grape bundle bundles up all active submodules in your repository, according to their
    respective .grapeconfig files.


    Usage:
       grape-bundle [--noRecurse] [--branches=<config.patch.branches>]
                    [--tagprefix=<config.patch.tagprefix>]
                    [--describePattern=<config.patch.describePattern>]
                    [--name=<config.repo.name>]
                    [--outfile=<fname>]
                    [--bundleTags=<branchToTagPatternMapping>]
                    [--submoduleBranches=<config.patch.submodulebranches>]


    Options:
       --noRecurse                      bundle only current level
       --branches=<list>                the space delimited list of branches to bundle.
                                        [default: .grapeconfig.patch.branches]
       --tagprefix=<str>                the prefix used to tag start points to bundle
                                        [default: .grapeconfig.patch.tagprefix]
       --describePattern=<pattern>      passed to git describe to aid in naming the bundle.
                                        [default: .grapeconfig.patch.describePattern]
       --name=<str>                     Name used as a prefix to the bundle file.
                                        [default: .grapeconfig.repo.name]
       --outfile=<fname>                Name of the output bundle file. Default behavior is to
                                        use branch names, the repo name, and output of git-describe
                                        to construct a name. Note that the default file name carries
                                        semantics for grape unbundle in determining which branches to
                                        update.
       --bundleTags=<mapping>           A list of branch:tagPattern tags to bundle. Note that a broadly defined tag
                                        pattern may yield larger bundle files than you might expect.
                                        [default: .grapeconfig.patch.branchToTagPatternMapping]
       --submoduleBranches=<list>       space delimited list of submodule branches to bundle.
                                        [default: .grapeconfig.patch.submodulebranches]


    .grapeConfig Defaults:

    [patch]
    branches = master
    tagprefix = patched
    describePattern = v*
    submodulebranches = master


    [repo]
    name = None


    """
    def __init__(self):
        super(Bundle, self).__init__()
        self._key = "bundle"
        self._section = "Patches"

    def config(self):
        return config_parser_global.grapeConfig()

    def description(self):
        # since bundle calls grape recursively, we give it configuration based on current repository semantics,
        # whereas grape typically has full workspace semantics.
        name = self.config().get(self.SECTION_PATCH, "tagprefix")
        description = "Create a bundle of branches listed in " + \
                      f"patch.branches since the '{name}/<branch>' tags"
        return description

    @log_wrapper
    def execute(self, args):

        tagprefix = args["--tagprefix"]
        branches = args["--branches"]

        reponame = args["--name"]
        describePattern = args["--describePattern"]

        launchArgs = {}

        tagsToBundle = config_parser_base.GrapeConfigParserBase.parseConfigPairList(args["--bundleTags"])
        recurse = not args["--noRecurse"]

        # Fetch only tags, so the workspace is consistent with last grape up
        git.fetch("origin '+refs/tags/*:refs/tags/*'", execution_path=self.workspace_dir)
        branchlist = branches.split()

        branchToTagMap = {}
        for branch in branchlist:
            versionTag = git.describe(f"--always --match '{describePattern}' {branch}", execution_path=self.workspace_dir)
            branchToTagMap[branch] = versionTag

        launchArgs["branchList"] = branchlist
        launchArgs["tags"] = tagsToBundle
        launchArgs["prefix"] = tagprefix
        launchArgs["describePattern"] = describePattern
        launchArgs["submoduleReverseBranchMap"] = None
        launchArgs["nestedSubprojectBranchToTagMap"] = branchToTagMap
        launchArgs["--outfile"] = args["--outfile"]

        otherCommandLauncher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
            bundlecmd, skipSubmodules=True, runInSubmodules=False,
            runInSubprojects=recurse, globalArgs=launchArgs,
            workspace_dir=self.workspace_dir)

        otherCommandLauncher.launchFromWorkspaceDir(handleMRE=bundlecmdMRE)

        if recurse:
            subbranchlist = args["--submoduleBranches"].split()
            subpublicmapping = config_parser_workspace.GrapeConfigParserWorkspace(self.workspace_dir).getMapping(Option.SECTION_WORKSPACE, "submodulepublicmappings")
            submoduleReverseBranchMap = {}
            found = False
            for branch in subbranchlist:
                for key, value in subpublicmapping.items():
                    if branch == value: 
                        submoduleReverseBranchMap[branch] = key
                        found = True
                        break
            if not found:
                logging.info(f"submodule branch {branch} was not found in submodule public mapping" +
                             " and will not be checked for consistency!")

            launchArgs["branchList"] = subbranchlist
            launchArgs["submoduleReverseBranchMap"] = submoduleReverseBranchMap
            launchArgs["nestedSubprojectBranchToTagMap"] = None

            submoduleCommandLauncher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
                bundlecmd, runInSubmodules=recurse, runInSubprojects=False,
                skipSubmodules=not recurse, runInOuter=False,
                globalArgs=launchArgs, workspace_dir=self.workspace_dir)
            submoduleCommandLauncher.launchFromWorkspaceDir(
                handleMRE=bundlecmdMRE, noPause=True)

        return True


    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_PATCH)
        config.set(self.SECTION_PATCH, 'tagprefix', 'patched')
        config.set(self.SECTION_PATCH, 'describePattern', 'v*')
        config.set(self.SECTION_PATCH, 'branches', 'master')
        config.set(self.SECTION_PATCH, 'branchmappings', '?:?')
        config.set(self.SECTION_PATCH, 'branchToTagPatternMapping', '?:v*')
        config.set(self.SECTION_PATCH, 'submodulebranches', 'master')
        config.set(self.SECTION_PATCH, 'submodulebranchmappings', '?:?')


def bundlecmd(repo='', branch='', args={}, *, workspace_dir):
    execution_path = repo
    branchlist = args["branchList"]
    tagsToBundle = args["tags"]
    tagprefix = args["prefix"]
    describePattern = args["describePattern"]
    submoduleReverseBranchMap = args["submoduleReverseBranchMap"]
    nestedSubprojectBranchToTagMap = args["nestedSubprojectBranchToTagMap"]

    reponame = os.path.split(repo)[1]
    logging.debug(f"bundlecmd called with {repo}, {execution_path}, {branchlist}")
    allBranches = git.allBranches(execution_path=execution_path)
    for branch in branchlist:
        remoteRef = git.join_list_as_git_path(['remotes', 'origin', branch])
        if remoteRef.strip() not in allBranches:
            logging.info(f"Branch {branch} in {repo} does not exist." +
                         f"This is only ok if {repo} was added after or removed before {branch}.")
            continue
        # ensure branch can be fast forwardable to origin/branch and do so
        if not git.safeForceBranchToOriginRef(branch, execution_path=execution_path):
            logging.info(f"*** Branch {branch} in {repo} has diverged from " +
                         "or is ahead of origin. Sync branches before bundling.")
            continue
        
        # check to ensure that submodule gitlinks are consistent
        if submoduleReverseBranchMap:
            if branch in submoduleReverseBranchMap.keys():
                top_branch = submoduleReverseBranchMap[branch]
                rel_path = os.path.relpath(repo, start=workspace_dir)
                gitlinkSHA = git.SHA(f"origin/{top_branch}:{rel_path}", execution_path=workspace_dir)
                SHA = git.SHA(f"origin/{branch}", execution_path=repo)
                if gitlinkSHA != SHA:
                    logging.info(f"*** Branch {branch} in {rel_path} inconsistent with gitlink on {top_branch}." 
                                 + " Rerun grape up and retry bundle.")

        tagname = f"{tagprefix}/{branch}"
        try:
            previousLocation = git.describe(
                f"--always --match '{describePattern}' {tagname}",
                execution_path=execution_path)
        except:
            # We should only get here if the tagname does not exist
            previousLocation = "unknown"
        try:
            currentLocation = git.describe(
                f"--always --match '{describePattern}' {branch}",
                execution_path=execution_path)
        except:
            logging.warning(f"Unable to locate {branch} in {reponame}!" +
                            " Something may be wrong...")
            currentLocation = branch
        if previousLocation.strip() != currentLocation.strip():
            if nestedSubprojectBranchToTagMap and currentLocation != branch:
                # Check to see if the tag in the nested subprojects differs from top level
                outerTag = nestedSubprojectBranchToTagMap[branch]
                if outerTag != currentLocation:
                    try:
                        outerLog = git.log(f"{currentLocation}..{outerTag}", execution_path=workspace_dir)
                        if not outerLog:
                            # If there are multiple tags associated with the current location, check for another tag.
                            # This is to handle the case where the production and development branch are in the same place.

                            # Get SHA of current location (use rev-list in case the location is a tag)
                            currentSHA = git.gitcmd(f"rev-list -n 1 {currentLocation}", "Rev-list failed", execution_path=execution_path)
                            # Get the next matching tag, if any. If there is not another matching tag, this may have the
                            # form <tag>-g<SHA>, which will fail in the git log call.
                            currentLocation2 = git.describe(
                                f"--always --exclude {currentLocation} --match '{describePattern}' {branch}",
                                execution_path=execution_path)

                            # Get SHA of second location (use rev-list in case the location is a tag)
                            currentSHA2 = git.gitcmd(f"rev-list -n 1 {currentLocation2}", "Rev-list failed", execution_path=execution_path)
                    
                            # Make sure that our second tag is the same commit as the original tag
                            if currentSHA == currentSHA2:
                                logging.info(f"*** {currentLocation} is the same as {currentLocation2} in {reponame}."
                                             + f" Checking {currentLocation2} against {outerTag}...")
                                # Check the second tag against the outer level tag
                                if outerTag == currentLocation2:
                                    # Second tag matches outer tag, so we are consistent.
                                    outerLog = True
                                    logging.info(f"    {currentLocation2} matches in top level.")
                                else:
                                    # Check to see if the second tag is in the history of the outerTag.
                                    try:
                                        outerLog = git.log(f"{currentLocation2}..{outerTag}", execution_path=workspace_dir)
                                        if outerLog:
                                            logging.info(f"    {currentLocation2} is in the history of {outerTag} in top level.")
                                    except grape_errors.GrapeGitError:
                                        # If there was no second tag, git log will fail
                                        pass

                            if not outerLog:
                                logging.info(f"*** {reponame} is tagged {currentLocation}, which is ahead of {outerTag} in the top level."
                                             + " Rerun grape up and retry bundle.")
                    except:
                        logging.info(f"*** Top level does not contain tag for {currentLocation} from {reponame}."
                                         + " Not checking for nested subproject consistency.")
            try:
                git.shortSHA(tagname, execution_path=execution_path)
                revlists = f" {tagname}..{branch}"
            except:
                logging.info(f"{tagname} does not exist in {reponame}, " +
                             f"bundling entire branch {branch}")
                revlists = f" {branch}"
            bundlename = args["--outfile"]
            if not bundlename:
                bundlename = f"{reponame}.{branch.replace('/', '.')}-" + \
                             f"{previousLocation}-{currentLocation}.bundle"
            logging.info(f"creating bundle {bundlename} in {reponame}")
            git.bundle(f"create {bundlename} {revlists} " +
                       f"--tags={tagsToBundle[branch]} ", execution_path=execution_path)
        else:
            logging.debug(f"{previousLocation} the same as {currentLocation} in {reponame}, no bundle necessary.")
    return True

def bundlecmdMRE(mre):
    logging.warning(mre)

    try:
        raise mre
    except grape_errors.MultiRepoException as errors:
        logging.warning("WARNING: ERRORS WERE GENERATED DURING GRAPE BUNDLE")
        for e, b in zip(errors.exceptions(), errors.branches()):
            logging.error(f"{b} {e}")


class Unbundle(Option, WorkspaceDirHandler):
    """
    grape unbundle


    Usage:
       grape-unbundle  [--branchMappings=<config.patch.branchMappings>]
                       [--submoduleBranchMappings=<config.patch.submoduleBranchMappings>]
                       [--noRecurse]

    Options:
        --branchMappings=<pairlist>   the branch mappings to pass to git fetch to unpack
                                      objects from the bundle file.
                                      [default: .grapeconfig.patch.branchMappings]
        --submoduleBranchMappings=<pairlist>   the branch mappings to pass to git fetch to unpack
                                      objects from the bundle file.
                                      [default: .grapeconfig.patch.submodulebranchmappings]
        --noRecurse                   do not recurse into submodules and nested subprojects

    """
    def __init__(self):
        super(Unbundle, self).__init__()
        self._key = "unbundle"
        self._section = "Patches"


    def description(self):
        return "Unbundle the given bundle into this repo, update all updated branches"

    def execute(self, args):
        recurse = not args["--noRecurse"]
        launchArgs = {}
        launchArgs["--branchMappings"] = args["--branchMappings"]
        repoLauncher =  multi_repo_cmd_launcher.MultiRepoCommandLauncher(
            unbundlecmd, skipSubmodules=True, runInSubmodules=False,
            runInSubprojects=recurse, globalArgs=launchArgs,
            workspace_dir=self.workspace_dir)
        repoLauncher.launchFromWorkspaceDir(handleMRE=bundlecmdMRE)

        launchArgs["--branchMappings"] = args["--submoduleBranchMappings"]

        submoduleCommandLauncher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
            unbundlecmd, runInSubmodules=recurse, runInSubprojects=False,
            skipSubmodules=not recurse, runInOuter=False,
            globalArgs=launchArgs,
            workspace_dir=self.workspace_dir)
        submoduleCommandLauncher.launchFromWorkspaceDir(
            handleMRE=bundlecmdMRE, noPause=True)

        return True

    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_PATCH)
        config.set(self.SECTION_PATCH, 'branchMappings', 'master:master')

def unbundlecmd(repo='', branch='', args={}, *, workspace_dir):
    execution_path = repo
    mappings = args["--branchMappings"]
    mapTokens = mappings.split()
    bundleNames = glob.glob(os.path.join(execution_path,"*.bundle"))
    for bundleName in bundleNames:
        mappings = ""
        for token in mapTokens:
            sourceDestPair = token.split(":")
            source = sourceDestPair[0]
            dest = sourceDestPair[1]
            bundleHeads = git.bundle(f"list-heads {bundleName}", execution_path=execution_path).split("\n")
            bundleBranches = []
            for line in bundleHeads:
                if "refs/heads" in line:
                    bundleBranches.append(line.split()[1].split("refs/heads/")[1])
            if source.replace('/', '.') in bundleBranches:
                mappings += f"{source}:{dest} "

        try:
            git.bundle(f"verify {bundleName}", execution_path=execution_path)
        except grape_errors.GrapeGitError as e:
            logging.error(e.gitCommand)
            logging.error(e.cwd)
            logging.error(e.gitOutput)
            raise e
        git.fetch(f"--tags -u {bundleName} {mappings}", execution_path=execution_path)
    return True
