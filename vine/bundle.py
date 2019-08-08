import glob
import logging
import os
from vine import config_parser_base
from vine import config_parser_global
from vine import grape_errors
from vine import grapeGit as git
from vine import multi_repo_cmd_launcher
from vine import option
from vine import utility
from vine import vine_logging
from vine.vine_logging import log_wrapper


# pull and merge in an up-to-date development branch
class Bundle(option.Option):

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

        git.fetch()
        git.fetch("--tags --force")
        branchlist = branches.split()

        launchArgs["branchList"] = branchlist
        launchArgs["tags"] = tagsToBundle
        launchArgs["prefix"] = tagprefix
        launchArgs["describePattern"] = describePattern
        launchArgs["--outfile"] = args["--outfile"]

        otherCommandLauncher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(bundlecmd, skipSubmodules=True, runInSubmodules=False,
                                                        runInSubprojects=recurse, globalArgs=launchArgs)

        otherCommandLauncher.launchFromWorkspaceDir(handleMRE=bundlecmdMRE)

        if recurse:
            launchArgs["branchList"] = args["--submoduleBranches"].split()
            submoduleCommandLauncher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(bundlecmd,
                                                                       runInSubmodules=recurse,
                                                                       runInSubprojects=False,
                                                                       skipSubmodules=not recurse,
                                                                       runInOuter=False,
                                                                       globalArgs=launchArgs
                                                                       )
            submoduleCommandLauncher.launchFromWorkspaceDir(handleMRE=bundlecmdMRE, noPause=True)

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


def bundlecmd(repo='', branch='', args={}):
    branchlist = args["branchList"]
    tagsToBundle = args["tags"]
    tagprefix = args["prefix"]
    describePattern = args["describePattern"]

    with git.cd(repo):
        reponame = os.path.split(repo)[1]
        for branch in branchlist:
            # ensure branch can be fast forwardable to origin/branch and do so
            if not git.safeForceBranchToOriginRef(branch):
                logging.info(f"Branch {branch} in {repo} has diverged from " +
                             "or is ahead of origin, or does not exist. " +
                             "Sync branches before bundling.")
                continue
            tagname = f"{tagprefix}/{branch}"
            try:
                previousLocation = git.describe(
                    f"--always --match '{describePattern}' {tagname}")
            except:
                # We should only get here if the tagname does not exist
                previousLocation = "unknown"
            try:
                currentLocation = git.describe(
                    f"--always --match '{describePattern}' {branch}")
            except:
                logging.warning(f"Unable to locate {branch} in {reponame}!" +
                                " Something may be wrong...")
                currentLocation = branch
            if previousLocation.strip() != currentLocation.strip():
                try:
                    git.shortSHA(tagname)
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
                           f"--tags={tagsToBundle[branch]} ")
    return True

def bundlecmdMRE(mre):
    logging.warning(mre)

    try:
        raise mre
    except grape_errors.MultiRepoException as errors:
        logging.warning("WARNING: ERRORS WERE GENERATED DURING GRAPE BUNDLE")
        for e, b in zip(errors.exceptions(), errors.branches()):
            logging.error(f"{b} {e}")


class Unbundle(option.Option):
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
        repoLauncher =  multi_repo_cmd_launcher.MultiRepoCommandLauncher(unbundlecmd, skipSubmodules=True, runInSubmodules=False,
                                                 runInSubprojects=recurse, globalArgs=launchArgs)
        repoLauncher.launchFromWorkspaceDir(handleMRE=bundlecmdMRE)
        launchArgs["--branchMappings"] = args["--submoduleBranchMappings"]
        submoduleCommandLauncher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(unbundlecmd,
                                                                                    runInSubmodules=recurse,
                                                                                    runInSubprojects=False,
                                                                                    skipSubmodules=not recurse,
                                                                                    runInOuter=False,
                                                                                    globalArgs=launchArgs
                                                                                    )
        submoduleCommandLauncher.launchFromWorkspaceDir(handleMRE=bundlecmdMRE, noPause=True)

        return True

    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_PATCH)
        config.set(self.SECTION_PATCH, 'branchMappings', 'master:master')

def unbundlecmd(repo='', branch='', args={}):
    mappings = args["--branchMappings"]
    mapTokens = mappings.split()
    with git.cd(repo):
        bundleNames = glob.glob("*.bundle")
        for bundleName in bundleNames:
            mappings = ""
            for token in mapTokens:
                sourceDestPair = token.split(":")
                source = sourceDestPair[0]
                dest = sourceDestPair[1]
                bundleHeads = git.bundle(f"list-heads {bundleName}").split("\n")
                bundleBranches = []
                for line in bundleHeads:
                    if "refs/heads" in line:
                        bundleBranches.append(line.split()[1].split("refs/heads/")[1])
                if source.replace('/', '.') in bundleBranches:
                    mappings += f"{source}:{dest} "

            try:
                git.bundle(f"verify {bundleName}")
            except grape_errors.GrapeGitError as e:
                logging.error(e.gitCommand)
                logging.error(e.cwd)
                logging.error(e.gitOutput)
                raise e
            git.fetch(f"--tags -u {bundleName} {mappings}")
    return True
