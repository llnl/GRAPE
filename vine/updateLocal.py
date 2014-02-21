import os, subprocess
import option
import grapeGit as git
# update the repo from the remote using the PyGitUp module
class UpdateLocal(option.Option):
    """
    grape up
    Updates the current branch and any public branches. 
    Usage: grape-up [--public=<branch>]

    Options:
    --public=<branch>       The publc branches to update in addition to the current one,
                            e.g. --public="master develop"
                            [default: .grapeconfig.flow.publicBranches ]


    """
    def __init__(self):
        self._key = "up"
        self._section = "Gitflow Tasks"

    def description(self):
        return "Update local branches that are tracked in your remote repo"

    def execute(self,args):
       print args
       fetchArgs = "origin "
       currentBranch = git.currentBranch()
       for pubBranch in args["--public"].split(' '): 
           if currentBranch != pubBranch:
               fetchArgs = fetchArgs+"%s:%s " % (pubBranch,pubBranch)
       git.fetch(fetchArgs)
       git.pull("origin %s"%currentBranch)
       return True
