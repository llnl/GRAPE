import option
import grapeGit as git


# update the repo from the remote using the PyGitUp module
class UpdateLocal(option.Option):
    """
    grape up
    Updates the current branch and any public branches. 
    Usage: grape-up [--public=<branch> ] [-v]

    Options:
    --public=<branch>       The public branches to update in addition to the current one,
                            e.g. --public="master develop"
                            [default: .grapeconfig.flow.publicBranches ]
    -v                      Be more verbose.


    """
    def __init__(self):
        super(UpdateLocal, self).__init__()
        self._key = "up"
        self._section = "Gitflow Tasks"

    def description(self):
        return "Update local branches that are tracked in your remote repo"

    def execute(self, args):
        quiet = not args["-v"]
        git.fetch("--prune", quiet=quiet)
        git.fetch("--tags", quiet=quiet)
        fetchArgs = "origin "
        currentBranch = git.currentBranch().strip()
        for pubBranch in args["--public"].split():
            if currentBranch != pubBranch.strip():
                fetchArgs += "%s:%s " % (pubBranch, pubBranch)
        try:
            git.fetch(fetchArgs)
        except git.GrapeGitError as e:
            # let non-fast-forward fetches slide
            if "rejected" in e.gitOutput and "non-fast-forward" in e.gitOutput:
                print("GRAPE WARNING: one or more of your public branches have local commits! "
                      "Did you forget to create a topic branch?")
                pass
            else:
                raise e
        
        try:
            if currentBranch.strip() != "HEAD": 
                git.pull("origin %s" % currentBranch)
        except git.GrapeGitError:
            print("Could not pull %s from origin. Maybe you haven't pushed it yet?" % currentBranch)
        return True

    def setDefaultConfig(self, config):
        pass
