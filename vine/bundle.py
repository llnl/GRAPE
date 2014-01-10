import option
import grapeGit as git
import grapeConfig

# pull and merge in an up-to-date development branch
class Bundle(option.Option):
    def __init__(self):
        self._key = "bundle"
        self._section = "Patches"

    def description(self):
      name = grapeConfig.grapeConfig().get("patch","tagnames") 
      return "Create a bundle of the current branch since the '%s' tag" % name

    def execute(self):
      config = grapeConfig.grapeConfig()
      tagnames = config.get("patch","tagnames")
      branches = config.get("patch","branches")
      reponame = config.get("repo","name")
      describePattern = config.get("patch","describePattern")
      taglist = tagnames.split(" ")
      branchlist = branches.split(" ")
      revlists = ""
      for pair in zip(taglist,branchlist):
         revlists = revlists + " %s..%s"%(pair[0],pair[1])
      previousLocation = git.describe("--match %s %s" % (describePattern,name))
      currentLocation = git.describe("--match %s HEAD" % describePattern)
      git.bundle("create %s-%s-from%s-to%s.bundle %s..HEAD" % (reponame,currentBranch,previousLocation))
      return True

    def setDefaultConfig(self,config):
      config.add_section('patch')
      config.set('patch','tagnames','patched')
      config.set('patch','describePattern','v*')
      config.set('patch','branches','master')


