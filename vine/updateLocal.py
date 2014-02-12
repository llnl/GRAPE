import os, subprocess
import option
import grapeGit as git
# update the repo from the remote using the PyGitUp module
class UpdateLocal(option.Option):
    def __init__(self):
        self._key = "up"
        self._section = "Gitflow Tasks"

    def description(self):
        return "Update local branches that are tracked in your remote repo"

    def execute(self,args):
       git.fetch()
       return True
