import option
import os
import grapeGit as git
import grapeConfig
import utility


# update the repo from the remote using the PyGitUp module
class UpdateLocal(option.Option):
    """
    grape up
    Updates the current branch and any public branches. 
    Usage: grape-up [--public=<branch> ]
                    [--recurse | --norecurse]
                    [-v]
                    

    Options:
    --public=<branch>       The public branches to update in addition to the current one,
                            e.g. --public="master develop"
                            [default: .grapeconfig.flow.publicBranches ]
    --recurse               Update branches in submodules.
    --norecurse             Do not update branches in submodules.
    -v                      Be more verbose.


    """
    def __init__(self):
        super(UpdateLocal, self).__init__()
        self._key = "up"
        self._section = "Gitflow Tasks"

    def description(self):
        return "Update local branches that are tracked in your remote repo"

    def execute(self, args):
        baseDir = utility.workspaceDir()
        cwd = os.getcwd()

        config = grapeConfig.grapeConfig()
        recurse = config.getboolean("workspace", "manageSubmodules") or args["--recurse"]
        recurse = recurse and (not args["--norecurse"])

        self.fetchLocal(args, baseDir, cwd,
                        [x.strip() for x in args["--public"].split()])

        for subproject in grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes():
            self.fetchLocal(args, os.path.join(baseDir, subproject), cwd,
                            [x.strip() for x in args["--public"].split()])
        allsubmodules = git.getAllSubmodules()
        if len(allsubmodules) > 0: 
            subBranchMappings = config.getMapping("workspace", "submoduleTopicPrefixMappings")
            for submodule in allsubmodules:
                self.fetchLocal(args, os.path.join(baseDir, submodule), cwd,
                                [subBranchMappings[x.strip()] for x in args["--public"].split()])
        return True

    @staticmethod
    def fetchLocal(args, workingDir, cwd, branches):
        os.chdir(workingDir)
        quiet = not args["-v"]
        git.fetch("--prune", quiet=quiet)
        git.fetch("--tags", quiet=quiet)
        fetchArgs = "origin "
        currentBranch = git.currentBranch().strip()
        for pubBranch in branches:
            if currentBranch != pubBranch:
                fetchArgs += "%s:%s " % (pubBranch, pubBranch)
        try:
            git.fetch(fetchArgs, quiet=quiet)
        except git.GrapeGitError as e:
            # let non-fast-forward fetches slide
            if "rejected" in e.gitOutput and "non-fast-forward" in e.gitOutput:
                print("GRAPE WARNING: one or more of your public branches have local commits! "
                      "Did you forget to create a topic branch?")
                pass
            else:
                os.chdir(cwd)
                raise e
        
        try:
            if currentBranch.strip() != "HEAD": 
                git.pull("origin %s" % currentBranch)
        except git.GrapeGitError:
            print("Could not pull %s from origin. Maybe you haven't pushed it yet?" % currentBranch)

        os.chdir(cwd)

    def setDefaultConfig(self, config):
        pass
