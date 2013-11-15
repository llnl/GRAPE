import os, subprocess
import option

# update the repo from the remote using the PyGitUp module
class UpdateLocal(option.Option):
    key = "up"
    section = "GITFLOW TASKS"

    def Description(self):
        return "Update local branches that are tracked in your remote repo"

    def Execute(self):
        gitup = os.path.join(os.path.dirname(__file__),"PyGitUp","gitup.py")

        p = subprocess.Popen(gitup,shell=True)
        p.wait()
        return True
