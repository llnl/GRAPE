import os
import ConfigParser
# vine imports
import option
import grapeGit as git
import utility
import grapeConfig

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
       grape-bundle [--norecurse] [--branches=<config.patch.branches>]
                    [--tagprefix=<config.patch.tagprefix>]
                    [--describePattern=<config.patch.describePattern>]
                    [--name=<config.repo.name>]
                    [--outfile=<fname>]


    Options:
       --norecurse                      bundle only current level
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
                                        to construct a name. Note that the default file name carrys
                                        semantics for grape unbundle in determining which branches to
                                        update.

    .grapeConfig Defaults:

    [patch]
    branches = master develop
    tagprefix = patched
    describePattern = v*

    [repo]
    name = None


    """
    def __init__(self):
        super(Bundle, self).__init__()
        self._key = "bundle"
        self._section = "Patches"

    def description(self):
        name = grapeConfig.grapeConfig().get("patch", "tagprefix")
        return "Create a bundle of branches listed in patch.branches since the '%s/<branch>' tags" % name

    def execute(self, args):
        tagprefix = args["--tagprefix"]
        branches = args["--branches"]
        reponame = args["--name"]
        describePattern = args["--describePattern"]

        if not args["--norecurse"]: 
            os.chdir(git.baseDir())
            grapecmd = os.path.join(os.path.dirname(__file__), "..", "grape")
            git.gitcmd("submodule foreach '%s bundle '" % grapecmd, "recursive submodule bundle failed")
        git.fetch()
        git.fetch("--tags")
        branchlist = branches.split()
        revlists = ""
        previousLocations = []
        currentLocations = []
        changedBranches = []
        for branch in branchlist:
            # ensure branch can be fast forwardable to origin/branch and do so
            if not git.safeForceBranchToOriginRef(branch):
                print("Branch %s has diverged from or is ahead of origin. Sync branches before bundling." % branch) 
                return False
            tagname = "%s/%s" % (tagprefix, branch)
            previousLocation = git.describe("--match '%s' %s" % (describePattern, tagname), quiet=True)
            currentLocation = git.describe("--match '%s' %s" % (describePattern, branch), quiet=True)
            if previousLocation.strip() != currentLocation.strip():
                revlists += " %s..%s" % (tagname, branch)
                previousLocations.append(previousLocation)
                currentLocations.append(currentLocation)
                changedBranches.append(branch)
        rangeString = ""
        for b in zip(changedBranches, previousLocations, currentLocations):
            rangeString += "%s-%s-%s." % (b[0].replace('/', '.'), b[1], b[2])
        bundlename = args["--outfile"]
        if not bundlename:
            bundlename = "%s.%sbundle" % (reponame, rangeString)
        if len(previousLocations) > 0: 
            git.bundle("create %s %s --tags --branches" % (bundlename, revlists))
        return True

    def setDefaultConfig(self, config):
        try: 
            config.add_section('patch')
        except ConfigParser.DuplicateSectionError:
            pass
        config.set('patch', 'tagprefix', 'patched')
        config.set('patch', 'describePattern', 'v*')
        config.set('patch', 'branches', 'master')


class Unbundle(option.Option):
    """
    grape unbundle


    Usage:
       grape-unbundle <grapebundlefile> [--branchMappings=<config.patch.branchMappings>]

    Arguments:
        <grapebundlefile>             The name of the grape bundle file to unbundle.

    Options:
        --branchMappings=<pairlist>   the branch mappings to pass to git fetch to unpack
                                      objects from the bundle file.
                                      [default: .grapeconfig.patch.branchMappings]

    """
    def __init__(self):
        super(Unbundle, self).__init__()
        self._key = "unbundle"
        self._section = "Patches"

    def description(self):
        return "Unbundle the given bundle into this repo, update all updated branches"

    def execute(self, args):
        bundleName = args["<grapebundlefile>"]
        mappings = args["--branchMappings"]
        
        mapTokens = mappings.split()
        mappings = ""
        for token in mapTokens:
            sourceDestPair = token.split(":") 
            source = sourceDestPair[0]
            dest = sourceDestPair[1]
            if source.replace('/', '.') in bundleName:
                mappings += "%s:%s " % (source, dest)
        try:
            git.bundle("verify %s" % bundleName)
        except git.GrapeGitError as e:
            print e.gitCommand
            print e.cwd
            print e.gitOutput
            return False
        git.fetch("-u %s %s" % (bundleName, mappings), quiet=False)
        
    def setDefaultConfig(self, config):
        try: 
            config.add_section('patch')
        except ConfigParser.DuplicateSectionError:
            pass
        config.set('patch', 'branchMappings', 'master:master')
