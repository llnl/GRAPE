import option
import utility
import types
import grapeGit as git
import grapeMenu

class NewBranchOption(option.Option): 
    """
    grape <newtopicbranch>
    Creates a new topic branch <type>/<username>/<descr> off of a public <branch>, where <type> is read from 
    one of the <type>:<branch> pairs found in .grapeconfig.flow.topicPrefixMappings.

    Usage: grape-<type> [--start=<branch>] [--user=<username>] [--noverify] [<descr>]

    Options:
    --user=<username>       The user developing this branch. Asks by default. 
    --start=<branch>        The start point for this branch. Default comes from .grapeconfig.flow.topicPrefixMappings. 
    --noverify              By default, grape will ask the user to verify the name and start point of the branch. 
                            This disables the verification. 
    
    Arguments:
    <name>                  Single word description of work being done on this branch. Asks by default.


    """
    def __init__(self,topic,public): 
        self._key = topic
        self._section = "Gitflow Tasks"
        self._public = public

    def description(self):
        return "Create and switch to a %s branch off of %s" % (self._key,self._public)

    def createBranch(branchPoint, prefix,user,descr,noverify):
        branch = descr if descr else utility.userInput("Enter new branch name")
        user = user if user else utility.getUserName()
        fullBranch = prefix+"/"+user+"/"+branch
        proceed = noverify or userInput("About to create branch "+fullBranch+" off of "+branchPoint+".\nProceed? [y/n]",'y')
        if (proceed):
            git.checkout("-b %s %s " % (fullBranch,branchPoint))
            git.push("-u origin %s" % fullBranch)
        else:
            print("Branch not created")

    def execute(self,args): 
        grapeMenu.menu().applyMenuChoice('up',['up'])
        start = args["--start"]
        if not start: 
            start = self._public

        createBranch(start,self._key,args['--user'],args['<descr>'],args['--noverify'])

class NewBranchOptionFactory():
    def __init__(self):
        pass

    def createNewBranchOptions(self,config):
        
        topicPublicMapping = utility.parseConfigPairList(config.get('flow','topicPrefixMappings'))
        options = []
        for topic in topicPublicMapping.keys():
            if topic != '?': 
                options.append(NewBranchOption(topic,topicPublicMapping[topic]))
        return options
