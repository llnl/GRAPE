import os
import option
import utility
import types
import grapeGit as git
import grapeMenu
import grapeConfig

class Publish(option.Option): 
    """
    grape publish
    Merges/Squash-merges/Rebases the current topic branch <type>/<username>/<descr> into the public <branch>, 
    where <public> is read from one of the <type>:<public> pairs found in .grapeconfig.flow.topicPrefixMappings and 
    .grapeconfig.workspace.submoduleTopicPrefixMappings.

    Usage: grape-publish [(--squash [--cascade --cm <msg>]| --merge) -m <msg>  | --rebase]
                         [--recurse | --norecurse] 
                         [<public>]

    Options:
    --squash        Squash merges the topic into the public, then performs a commit if the merge goes clean. 
    --cascade       For squash merges, can choose to cascade back to the topic branch after the merge is completed. 
    --merge         Perform a normal merge. 
    -m <msg>        The commit message to use for a successful merge / squash merge. 
    --rebase        Rebases the topic branch to the public, then fast forwards the public to the tip of the topic. 
    --recurse       Perform the publish action in submodules. 
                    True if .grapeconfig.workspace.manageSubmodules is True. 
    --norecurse     Do not perform the publish action in submodules. 
                    True if .grapeconfig.workspace.manageSubmodules is False. 
    
    Optional Arguments:
    <public>        The branch to publish to. Defaults to the mapping for the current topic branch as described by
                    .grapeconfig.flow.topicPrefixMappings. 


    """
    def __init__(self)
        self._key = "publish"
        self._section = "Gitflow Tasks"

    def description(self):
        topicPublicMapping = utility.parseConfigPairList(config.get('flow','topicPrefixMappings'))
        currentBranch = git.currentBranch()
        prefix = currentBranch.split('/')[0]
        public = topicPublicMapping[prefix]
        return "Publish the current topic branch to %s" %public


    def execute(self,args): 
        print args
        exit(0)
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
        
        if (subArgs and recurse): 
            submapping = grapeConfig.grapeConfig().get('workspace','submoduleTopicPrefixMappings')
            submapping = utility.parseConfigPairList(submapping)
            submodulePublic = submapping[self._key]
            proceed = args["--noverify"] or utility.userInput("About to create the branch off of "+submodulePublic+" for all submodules.\nProceed? [y/n]",'y') 
            if proceed:
                for sub in git.getSubmodules(): 
                    os.chdir(os.path.join(cwd,sub))
                    grapeMenu.menu().applyMenuChoice('up',['up','--public="ale3d"'])
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
        
        topicPublicMapping = utility.parseConfigPairList(config.get('flow','topicPrefixMappings'))
        options = []
        for topic in topicPublicMapping.keys():
            if topic != '?': 
                options.append(NewBranchOption(topic,topicPublicMapping[topic]))
        return options
