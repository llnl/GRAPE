import os
import option
import grapeGit as git
import grapeConfig, config
import ConfigParser

# pull and merge in an up-to-date development branch
class Bundle(option.Option):
    def __init__(self):
        self._key = "bundle"
        self._section = "Patches"

    def description(self):
        name = grapeConfig.grapeConfig().get("patch","tagprefix") 
        return "Create a bundle of branches listed in patch.branches since the '%s/<branch>' tags" % name

    def execute(self):
        os.chdir(git.baseDir())
        grapecmd = os.path.join(os.path.dirname(__file__),"..","grape")
        git.gitcmd("submodule foreach '%s bundle'" % grapecmd,"recursive submodule bundle failed") 
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
                print("Branch %s has diverged from or is ahead of origin. Sync branches before bundling.") 
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
        fetchOutput = git.fetch("%s %s" % (bundleName,grapeConfig.grapeConfig().get('patch','branchMappings'))) 
        

    def setDefaultConfig(self,config): 
        try: 
            config.add_section('patch')
        except ConfigParser.DuplicateSectionError:
            pass
        config.set('patch','branchMappings','master:master')


