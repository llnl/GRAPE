import os
import option
import grapeGit as git
import grapeConfig, config
import ConfigParser
import utility

#if utility.grapeDir() not in sys.path(): 
#    sys.path.append(utility.grapeDir())
from docopt.docopt import docopt


"""
grape [un]bundle

Usage:
    grape bundle [--recurse  | --norecurse] [--branches=<config.patch.branches>] 
                 [--tagprefix=<config.patch.tagprefix>]
                 [--describePattern=<config.patch.describePattern>]
                 [--name=<config.repo.name>]
                  
    grape unbundle <grapebundlefile> [--mappings=master:master]

Generic options:
    -h, --help

Options:
    --recurse               recurse into submodules (default)
    --norecurse             bundle only current level
    --branches              the space delimited list of branches to bundle. 
                            Default from .grapeconfig  patch.branches . 
    --tagprefix             the prefix used to tag start points to bundle
                            Default from .grapeconfig patch.tagprefix . 
    --describePattern       passed to git describe to aid in naming the bundle. 
                            Default from .grapeconfig patch.describePattern. 
    --name                  Name used as a prefix to the bundle file. 
                            Default from .grapeconfig repo.name

"""

# pull and merge in an up-to-date development branch
class Bundle(option.Option):

    """
grape [un]bundle

    
Usage:
   grape-bundle [--norecurse] [--branches=<config.patch.branches>] 
                [--tagprefix=<config.patch.tagprefix>]
                [--describePattern=<config.patch.describePattern>]
                [--name=<config.repo.name>]

Generic options:
   -h, --help

Options:
   --norecurse                      bundle only current level 
   --branches=<list>                the space delimited list of branches to bundle. 
                                    Default from .grapeconfig  patch.branches . 
   --tagprefix=<str>                the prefix used to tag start points to bundle
                                    Default from .grapeconfig patch.tagprefix . 
   --describePattern=<pattern>      passed to git describe to aid in naming the bundle. 
                                    Default from .grapeconfig patch.describePattern. 
   --name=<str>                     Name used as a prefix to the bundle file. 
                                    Default from .grapeconfig repo.name

.grapeConfig Defaults: 

[patch] 
branches = master develop
tagprefix = patched
describePattern = v*

[repo]
name = None


    """
#    """
#grape [un]bundle
#    
#Usage: grape-bundle 
#
#Generic options:
#   -h, --help
#
#
#    """

    def __init__(self):
        self._key = "bundle"
        self._section = "Patches"

    def description(self):
        name = grapeConfig.grapeConfig().get("patch","tagprefix") 
        return "Create a bundle of branches listed in patch.branches since the '%s/<branch>' tags" % name

    def execute(self,argv):
        args = docopt(Bundle.__doc__,argv=argv[1:])
        os.chdir(git.baseDir())
        if not args["--norecurse"]: 
            grapecmd = os.path.join(os.path.dirname(__file__),"..","grape")
            git.gitcmd("submodule foreach '%s bundle %s'" % (grapecmd,' '.join(argv)),"recursive submodule bundle failed") 
        git.fetch()
        git.fetch("--tags")
        config = grapeConfig.grapeConfig()
        tagprefix = config.get("patch","tagprefix")
        branches = config.get("patch","branches")
        reponame = config.get("repo","name")
        describePattern = config.get("patch","describePattern")
        branchlist = branches.split(" ")
        revlists = ""
        previousLocations = []
        currentLocations = []
        changedBranches = []
        for branch in branchlist:
            # ensure branch can be fast forwardable to origin/branch and do so
            if not git.safeForceBranchToOriginRef(branch):
                print("Branch %s has diverged from or is ahead of origin. Sync branches before bundling." % branch) 
                return False
            tagname = "%s/%s" % (tagprefix,branch)
            previousLocation = git.describe("--match '%s' %s" % (describePattern,tagname))
            currentLocation = git.describe("--match '%s' %s" % (describePattern,branch))
            if (previousLocation.strip() != currentLocation.strip()):
                revlists = revlists + " %s..%s"%(tagname,branch)
                previousLocations.append(previousLocation)
                currentLocations.append(currentLocation)
                changedBranches.append(branch)
        rangeString = ""
        for b in zip(changedBranches,previousLocations,currentLocations):
            rangeString = rangeString + "%s-%s-%s." % (b[0],b[1],b[2]) 
        bundlename = "%s.%sbundle" % (reponame,rangeString)
        if len(previousLocations) > 0: 
            git.bundle("create %s %s --tags --branches" % (bundlename,revlists))
        return True

    def setDefaultConfig(self,config):
        try: 
            config.add_section('patch')
        except ConfigParser.DuplicateSectionError:
            pass
        config.set('patch','tagprefix','patched')
        config.set('patch','describePattern','v*')
        config.set('patch','branches','master')

class Unbundle(option.Option): 
    def __init__(self):
        self._key = "unbundle"
        self._section = "Patches"

    def description(self):
       return "Unbundle the given bundle into this repo, update all updated branches" 

    def execute(self,args = None):
        bundleName = args[0] if args else utility.getUserInput("Enter name of bundle to bundle")
        mappings = grapeConfig.grapeConfig().get('patch','branchMappings')
        mapTokens = mappings.split(' ')
        mappings = ""
        for token in mapTokens:
            sourceDestPair = token.split(":") 
            source = sourceDestPair[0]
            dest = sourceDestPair[1]
            if source in bundleName: 
               mappings = mappings + "%s:%s " % (source,dest)
        git.bundle("verify %s" % bundleName)
        fetchOutput = git.fetch("-u %s %s" % (bundleName,mappings)) 
        

    def setDefaultConfig(self,config): 
        try: 
            config.add_section('patch')
        except ConfigParser.DuplicateSectionError:
            pass
        config.set('patch','branchMappings','master:master')


