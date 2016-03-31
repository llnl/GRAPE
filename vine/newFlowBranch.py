import os
import option
import utility
import grapeGit as git
import grapeMenu
import grapeConfig


class NewBranchOption(option.Option):
    """
    grape <newtopicbranch>
    Creates a new topic branch <type>/<username>/<descr> off of a public <branch>, where <type> is read from 
    one of the <type>:<branch> pairs found in .grapeconfig.flow.topicPrefixMappings.

    Usage: grape-<type> [--start=<branch>] [--user=<username>] [--noverify] [--recurse | --noRecurse] [<descr>] 

    Options:
    --user=<username>       The user developing this branch. Asks by default. 
    --start=<branch>        The start point for this branch. Default comes from .grapeconfig.flow.topicPrefixMappings. 
    --noverify              By default, grape will ask the user to verify the name and start point of the branch. 
                            This disables the verification. 
    --recurse               Create the branch in submodules. 
                            [default: .grapeconfig.workspace.manageSubmodules]
    --noRecurse             Don't create the branch in submodules.
    
    Optional Arguments:
    <descr>                  Single word description of work being done on this branch. Asks by default.


    """
    def __init__(self, topic, public):
        super(NewBranchOption, self).__init__()
        self._key = topic
        self._section = "Gitflow Tasks"
        self._public = public

    def description(self):
        return "Create and switch to a %s branch off of %s" % (self._key, self._public)



    def execute(self, args):
        start = args["--start"]
        if not start: 
            start = self._public
            
        
        # decide whether to recurse
        recurse = grapeConfig.grapeConfig().get('workspace', 'manageSubmodules')
        if args["--recurse"]:
            recurse = True
        if args["--noRecurse"]:
            recurse = False

        
        if not args["<descr>"]:
            args["<descr>"] =  utility.userInput("Enter one word description for branch:")
            
        if not args["--user"]:
            args["--user"] = utility.getUserName()
            
        branchName = self._key + "/" + args["--user"] + "/" + args["<descr>"]

            
        launcher = utility.MultiRepoCommandLauncher(createBranch, 
                                                   runInSubmodules=recurse, 
                                                   runInSubprojects=recurse, 
                                                   runInOuter=True, 
                                                   branch=start, 
                                                   globalArgs=branchName)
        
        launcher.initializeCommands()
        utility.printMsg("About to create the following branches:")
        for repo, branch in zip(launcher.repos, launcher.branches):
            utility.printMsg("\t%s off of %s in %s" % (branchName, branch, repo))
        proceed = utility.userInput("Proceed? [y/n]", default="y")
        if proceed:
            grapeMenu.menu().applyMenuChoice('up', ['up', '--public=%s' % start])
            launcher.launchFromWorkspaceDir()
        else:
            utility.printMsg("branches not created")


    def setDefaultConfig(self, config):
        config.ensureSection("workspace")
        config.set('workspace', 'manageSubmodules', 'True')
        config.set('workspace', 'submoduleTopicPrefixMappings', '?:develop')





class NewBranchOptionFactory():
    def __init__(self):
        pass

    @staticmethod
    def createNewBranchOptions(config):
        
        topicPublicMapping = config.getMapping('flow', 'topicPrefixMappings')
        options = []
        for topic in topicPublicMapping.keys():
            if topic != '?': 
                options.append(NewBranchOption(topic, topicPublicMapping[topic]))
        return options




def createBranch(repo="unknown", branch="master", args=[]):
    branchPoint = branch
    fullBranch = args
    with utility.cd(repo):
        utility.printMsg("creating and switching to %s in %s" % (fullBranch, repo))
        try:
            git.checkout("-b %s %s " % (fullBranch, branchPoint))
        except git.GrapeGitError as e:
            print "%s:%s" % (repo, e.gitOutput)
            utility.printMsg("WARNING: %s in %s will not be pushed." % (fullBranch, repo))
            return
        utility.printMsg("pushing %s to origin in %s" % (fullBranch, repo))
        try:
            git.push("-u origin %s" % fullBranch)
        except git.GrapeGitError as e:
            print "%s:  %s" % (repo, e.gitOutput)
            return
            


if __name__ is "__main__":
    import grapeMenu
    menu = grapeMenu.menu()
    menu.applyMenuChoice("feature", [])
