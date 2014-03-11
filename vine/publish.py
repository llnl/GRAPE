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
    .grapeconfig.workspace.submoduleTopicPrefixMappings. The branch-dependent publish policy (merge vs. squash merge.
    vs rebase) is decided using grapeconfig.flow.publishPolicy for the top-level repo and the publish policy for 
    submodules is decided using grapeconfig.workspace.submodulePublishPolicy. 

    Usage: grape-publish [(--squash [--cascade ]| --merge) --rebase]
                         [-m <msg>]
                         [--recurse | --norecurse] 
                         [<public> [<submodulePublic>]] 
                         [--noverify]

    Options:
    --squash            Squash merges the topic into the public, then performs a commit if the merge goes clean. 
    --cascade           For squash merges, can choose to cascade back to the topic branch after the merge is completed. 
    --merge             Perform a normal merge. 
    -m <msg>            The commit message to use for a successful merge / squash merge. Ignored if used with --rebase. 
    --rebase            Rebases the topic branch to the public, then fast forwards the public to the tip of the topic. 
    --recurse           Perform the publish action in submodules. 
                        Defaults to True if .grapeconfig.workspace.manageSubmodules is True. 
    --norecurse         Do not perform the publish action in submodules. 
                        Defaults to True if .grapeconfig.workspace.manageSubmodules is False.
    --noverify          Set to skip interactive verification of publish commands. 
    
    Optional Arguments:
    <public>            The branch to publish to. Defaults to the mapping for the current topic branch as described by
                        .grapeconfig.flow.topicPrefixMappings. 
    <submodulePublic>   The branch to publish to in submodules. Defaults to the mapping for the current topic branch as
                        described by .grapeconfig.workspace.submoduleTopicPrefixMappings.
                        


    """
    def __init__(self):
        self._key = "publish"
        self._section = "Gitflow Tasks"

    def description(self):
        topicPublicMapping = utility.parseConfigPairList(grapeConfig.grapeConfig().get('flow','topicPrefixMappings'))
        currentBranch = git.currentBranch()
        prefix = currentBranch.split('/')[0]
        public = topicPublicMapping[prefix]
        return "Publish the current topic branch to %s" %public

    def merge(self,public,topic, args): 
        print("merging %s %s" % (public,topic))
        pass

    def squashMerge(self,public,topic,args): 
        print("squash merging %s %s" % (public,topic))
        pass

    def rebase(self,pulic,topic,args): 
        print("rebasing %s %s" % (public,topic))

        pass

    def publish(self,policy,public,topic,args): 
        policy = policy.strip().lower()
        if policy == "merge":
            self.merge(public,topic,args)
        if policy == "squash": 
            self.squashMerge(public,topic,args)
        if policy == "rebase": 
            self.rebase(public, topic,args)
        
    def execute(self,args): 
        print args
        # make sure public branches are up to date. 
        grapeMenu.menu().applyMenuChoice('up',['up'])

        # get the outer level public branch destination
        config = grapeConfig.grapeConfig()
        topic = git.currentBranch()
        topic2public = utility.parseConfigPairList(config.get('flow','topicPrefixMappings'))
        prefix = topic.split('/')[0]        

        public = args["<public>"]
        if not public:
            public = topic2public[prefix]
        
        # decide on the publish policy
        policyMappings = utility.parseConfigPairList(config.get('flow','publishPolicy'))
        policy = policyMappings[public]
        if args["--merge"]: 
            policy = "merge"
        if args["--squash"]: 
            policy = "squash"
        if args["--rebase"]:
            policy = "rebase"

        # decide whether to recurse into submodules
        recurse = grapeConfig.grapeConfig().get('workspace','manageSubmodules')
        if (args["--recurse"]): 
            recurse = True
        if (args["--norecurse"]): 
            recurse = False
        
        cwd = utility.workspaceDir()
        os.chdir(cwd)
        
        if (recurse): 
            submapping = config.get('workspace','submoduleTopicPrefixMappings')
            submapping = utility.parseConfigPairList(submapping)
            submodulePublic = submapping[prefix]
            submodulePolicy = config.get('workspace','submodulePublishPolicy')
            submodulePolicy = utility.parseConfigPairList(submodulePolicy)
            print submodulePolicy
            try: 
                submodulePolicy = submodulePolicy[submodulePublic]
            except KeyError:
                if '?' in submodulePolicy.keys(): 
                    submodulePolicy = submodulePolicy['?']


            proceed = args["--noverify"] or utility.userInput("About to publish the branch off of "+submodulePublic+" for all submodules.\nProceed? [y/n]",'y') 
            if proceed:
                for sub in git.getSubmodules(): 
                    os.chdir(os.path.join(cwd,sub))
                    
                    grapeMenu.menu().applyMenuChoice('up',['up','--public="%s"'%submodulePublic])
                    self.publish(submodulePolicy, submodulePublic,topic, args)

        proceed = args["--noverify"] or  utility.userInput("About to publish the branch off of "+public+" for top level workspace.\nProceed? [y/n]",'y') 
        self.publish(policy,public,topic,args)

         

    def setDefaultConfig(self,config): 
        try:
            config.add_section('workspace')
        except ConfigParser.DuplicateSectionError:
            pass
        try: 
            config.add_section('flow')
        except ConfigParser.DuplicateSectionError:
            pass


        config.set('workspace','manageSubmodules','True')
        config.set('workspace','submoduleTopicPrefixMappings','?:develop')
        config.set('workspace','submodulePublishPolicy','?:merge')
        config.set('flow','publishPolicy','?:merge')

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
