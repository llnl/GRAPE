import os
import option
import utility
import types
import grapeGit as git
import grapeMenu
import grapeConfig

class NewBranchOption(option.Option): 
    """
    grape <newtopicbranch>
    Creates a new topic branch <type>/<username>/<descr> off of a public <branch>, where <type> is read from 
    one of the <type>:<branch> pairs found in .grapeconfig.flow.topicPrefixMappings.

    Usage: grape-<type> [--start=<branch>] [--user=<username>] [--noverify] [--recurse | --norecurse] [<descr>] 

    Options:
    --user=<username>       The user developing this branch. Asks by default. 
    --start=<branch>        The start point for this branch. Default comes from .grapeconfig.flow.topicPrefixMappings. 
    --noverify              By default, grape will ask the user to verify the name and start point of the branch. 
                            This disables the verification. 
    --recurse               Create the branch in submodules. 
                            [default: .grapeconfig.workspace.manageSubmodules]
    --norecurse             Don't create teh branch in submodules. 
    
    Optional Arguments:
    <descr>                  Single word description of work being done on this branch. Asks by default.


    """
    def __init__(self,topic,public): 
        self._key = topic
        self._section = "Gitflow Tasks"
        self._public = public

    def description(self):
        return "Create and switch to a %s branch off of %s" % (self._key,self._public)

    def createBranch(self,branchPoint, prefix,user,descr,noverify):
        branch = descr if descr else utility.userInput("Enter new branch name")
        user = user if user else utility.getUserName()
        fullBranch = prefix+"/"+user+"/"+branch
        proceed = noverify or utility.userInput("About to create branch "+fullBranch+" off of "+branchPoint+".\nProceed? [y/n]",'y')
        if (proceed):
            git.checkout("-b %s %s " % (fullBranch,branchPoint))
            git.push("-u origin %s" % fullBranch)
            return (branchPoint,prefix,user,branch)
        else:
            print("Branch not created")
            return None

    def execute(self,args): 
        grapeMenu.menu().applyMenuChoice('up',['up'])
        start = args["--start"]
        recurse = grapeConfig.grapeConfig().get('workspace','manageSubmodules')
        if (args["--recurse"]): 
            recurse = True
        if (args["--norecurse"]): 
            recurse = False
        if not start: 
            start = self._public
        
        cwd = utility.workspaceDir()
        os.chdir(cwd)
        subArgs = self.createBranch(start,self._key,args['--user'],args['<descr>'],args['--noverify'])
        submodules = git.getSubmodules()
        recurse = recurse and submodules
        if (subArgs and recurse): 
            submapping = grapeConfig.grapeConfig().get('workspace','submoduleTopicPrefixMappings')
            submapping = grapeConfig.parseConfigPairList(submapping)
            try: 
                submodulePublic = submapping[self._key]
            except:
                submodulePublic = submapping['?']

            proceed = args["--noverify"] or utility.userInput("About to create the branch off of "+submodulePublic+" for all submodules.\nProceed? [y/n]",'y') 
            if proceed:
                for sub in submodules: 
                    os.chdir(os.path.join(cwd,sub))
                    git.checkout(submodulePublic)
                    grapeMenu.menu().applyMenuChoice('up',['up','--public=%s' % submodulePublic])
                    self.createBranch(submodulePublic,self._key,subArgs[2],subArgs[3],True)

    def setDefaultConfig(self,config):
        try:
            config.add_section('workspace')
        except ConfigParser.DuplicateSectionError:
            pass
        config.set('workspace','manageSubmodules','True')
        config.set('workspace','submoduleTopicPrefixMappings','?:develop')

class NewBranchOptionFactory():
    def __init__(self):
        pass

    def createNewBranchOptions(self,config):
        
        topicPublicMapping = grapeConfig.parseConfigPairList(config.get('flow','topicPrefixMappings'))
        options = []
        for topic in topicPublicMapping.keys():
            if topic != '?': 
                options.append(NewBranchOption(topic,topicPublicMapping[topic]))
        return options
