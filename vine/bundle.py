import os
import ConfigParser
import option
import grapeGit as git
import grape_errors
import utility
import config_parser_base
import config_parser_global
import global_state
import multi_repo_cmd_launcher

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
        return "Create a bundle of branches listed in patch.branches since the '%s/<branch>' tags" % name

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

    with utility.cd(repo):
        reponame = os.path.split(repo)[1]
        for branch in branchlist:
            # ensure branch can be fast forwardable to origin/branch and do so
            if not git.safeForceBranchToOriginRef(branch):
                print("Branch %s in %s has diverged from or is ahead of origin, or does not exist. Sync branches before bundling." % (branch, repo))
                continue
            tagname = "%s/%s" % (tagprefix, branch)
            try:
                previousLocation = git.describe("--always --match '%s' %s" % (describePattern, tagname))
            except:
                # We should only get here if the tagname does not exist
                previousLocation = "unknown"
            try:
                currentLocation = git.describe("--always --match '%s' %s" % (describePattern, branch))
            except:
                global_state.printMsg("Unable to locate %s in %s! Something may be wrong..." % (branch, reponame))
                currentLocation = branch
            if previousLocation.strip() != currentLocation.strip():
                try:
                    git.shortSHA(tagname)
                    revlists = " %s..%s" % (tagname, branch)
                except:
                    global_state.printMsg("%s does not exist in %s, bundling entire branch %s" % (tagname, reponame, branch))
                    revlists = " %s" % (branch)
                bundlename = args["--outfile"]
                if not bundlename:
                    bundlename = "%s.%s-%s-%s.bundle" % (reponame, branch.replace('/', '.'), previousLocation,
                                                         currentLocation)
                global_state.printMsg("creating bundle %s in %s" % (bundlename, reponame))
                git.bundle("create %s %s --tags=%s " % (bundlename, revlists, tagsToBundle[branch]))
    return True

def bundlecmdMRE(mre):
    print mre
    try:
        raise mre
    except  grape_errors.MultiRepoException as errors:
        global_state.printMsg("WARNING: ERRORS WERE GENERATED DURING GRAPE BUNDLE")
        for e, b in zip(errors.exceptions(), errors.branches()):
            print b, e


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

import glob
def unbundlecmd(repo='', branch='', args={}):
    mappings = args["--branchMappings"]
    mapTokens = mappings.split()
    with utility.cd(repo):
        bundleNames = glob.glob("*.bundle")
        for bundleName in bundleNames:
            mappings = ""
            for token in mapTokens:
                sourceDestPair = token.split(":")
                source = sourceDestPair[0]
                dest = sourceDestPair[1]
                bundleHeads = git.bundle("list-heads %s" % bundleName).split("\n")
                bundleBranches = []
                for line in bundleHeads:
                    if "refs/heads" in line:
                        bundleBranches.append(line.split()[1].split("refs/heads/")[1])
                if source.replace('/', '.') in bundleBranches:
                    mappings += "%s:%s " % (source, dest)

            try:
                git.bundle("verify %s" % bundleName)
            except grape_errors.GrapeGitError as e:
                print e.gitCommand
                print e.cwd
                print e.gitOutput
                raise e
            git.fetch("--tags -u %s %s" % (bundleName, mappings))
    return True
