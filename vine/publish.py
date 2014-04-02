import os
import option
import utility
import ConfigParser
import grapeGit as git
import grapeMenu
import grapeConfig
import subtree

class Publish(option.Option): 
    """
    grape publish
    Merges/Squash-merges/Rebases the current topic branch <type>/<username>/<descr> into the public <branch>, 
    where <public> is read from one of the <type>:<public> pairs found in .grapeconfig.flow.topicPrefixMappings and 
    .grapeconfig.workspace.submoduleTopicPrefixMappings. The branch-dependent publish policy (merge vs. squash merge.
    vs rebase) is decided using grapeconfig.flow.publishPolicy for the top-level repo and the publish policy for 
    submodules is decided using grapeconfig.workspace.submodulePublishPolicy. 

    Usage: grape-publish [--squash [--cascade ] | --merge |  --rebase]
                         [-m <msg>]
                         [--recurse | --norecurse] 
                         [<public> [<submodulePublic>]] 
                         [--noverify] 
                         [--nopush]
                         [--pushSubtrees | --noPushSubtrees]
                         [-v]

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
    --nopush            Set to skip the push of commits generated during the publish procedure.
    --pushSubtrees      Push subtrees to their respective remotes (.grapeconfig.subtree-<name>.remote) appropriate public
                        branches (.grapeconfig.subtree-<name>.topicPrefixMappings)
                        Set by default if .grapeconfig.subtrees.pushOnPublish is True.
    --noPushSubtrees    Don't perform a git subtree push.
    -v                  Be more verbose. 
    
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
        topicPublicMapping = grapeConfig.parseConfigPairList(grapeConfig.grapeConfig().get('flow','topicPrefixMappings'))
        currentBranch = git.currentBranch()
        prefix = currentBranch.split('/')[0]
        try: 
            public = topicPublicMapping[prefix]
        except KeyError:
            if '?' in topicPublicMapping.keys(): 
                public = topicPublicMapping['?']
        return "Publish the current topic branch to %s" %public

    def validateInput(self,policy,args):
        policy = policy.strip().lower()
        valid = False
        if policy == "merge" or policy == "squash": 
            valid = bool(args["-m"])
            if not valid:
                print("Commit message required for merge or squash merge publish policies.")
        if policy == "rebase":
            valid = True

        if not valid:
            print("Type grape publish -h for more details")
        return valid

    def merge(self,public,topic, args): 
        print("merging %s into %s" % (topic,public))
        git.checkout(public)
        git.merge("%s -m \"%s\" " % (topic,args["-m"]))
        print("%s merged successfully to %s" % (topic,public))
        print("You are currently on %s" %public)

    def squashMerge(self,public,topic,args): 
        print("squash merging %s into %s" % (topic,public))
        git.checkout(public)
        git.merge("--squash %s" % topic)
        git.commit("-m \"%s\"" % args["-m"])
        print("%s squash-merged successfully to %s" % (topic,public))
        print("You are currently on %s" % public)

    def rebase(self,pulic,topic,args): 
        print("rebasing %s onto %s" % (topic,public))
        git.rebase(public)
        print("%s successfully rebased onto %s" % (topic,public))
        print("You are currently on %s" % topic)

    def publish(self,policy,public,topic,args): 
        # don't bother publishing if public and topic are the same commit
        if git.shortSHA(public,quiet=True).strip() == git.shortSHA(topic,quiet=True).strip():
            git.checkout(public)
            return
        policy = policy.strip().lower()
        if policy == "merge":
            self.merge(public,topic,args)
        if policy == "squash": 
            self.squashMerge(public,topic,args)
        if policy == "rebase": 
            self.rebase(public, topic,args)

        if not args["--nopush"]: 
            git.push("-u origin HEAD")
        
    def execute(self,args): 
        # make sure public branches are up to date. 
        grapeMenu.menu().apply_menu_choice('up',['up'])

        quiet = not args["-v"]
        # get the outer level public branch destination
        config = grapeConfig.grapeConfig()
        topic = git.currentBranch()
        topic2public = grapeConfig.parseConfigPairList(config.get('flow','topicPrefixMappings'))
        prefix = topic.split('/')[0]        

        public = args["<public>"]
        if not public:
            public = topic2public[prefix]
        
        # set any CL defined publish policy
        policy = None
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
       
        # no need to recurse if there are no submodules
        recurse = recurse and git.getSubmodules()
        cwd = utility.workspaceDir()
        os.chdir(cwd)
        
        if (recurse): 
            submapping = config.get('workspace','submoduleTopicPrefixMappings')
            submapping = grapeConfig.parseConfigPairList(submapping)
            submodulePublic = submapping[prefix]
            
            # submodule policy is Command Line requested policy, otherwise is based on 
            #       .grapeconfig.workspace.submodulePublishPolicy
            submodulePolicy = policy
            if not submodulePolicy:
                submodulePolicy = config.get('workspace','submodulePublishPolicy')
                submodulePolicy = grapeConfig.parseConfigPairList(submodulePolicy)[submodulePublic]
            valid = self.validateInput(submodulePolicy,args) 
            proceed = valid and ( args["--noverify"] or utility.userInput("About to publish "+ topic +" to "+submodulePublic+" for all submodules.\nProceed? [y/n]",'y') )
            if proceed:
                for sub in git.getSubmodules(): 
                    os.chdir(os.path.join(cwd,sub))
                    
                    grapeMenu.menu().apply_menu_choice('up',['up','--public=%s'%submodulePublic])
                    self.publish(submodulePolicy, submodulePublic,topic, args)
            os.chdir(cwd)



                    
                

        # update policy from config if not set on CL
        if not policy:
            policy = grapeConfig.parseConfigPairList(config.get('flow','publishPolicy'))[public]

        valid = self.validateInput(policy,args)
        proceed = valid and (args["--noverify"] or  utility.userInput("About to publish " + topic + " to "+public+" for top level workspace.\nProceed? [y/n]",'y') )
        if proceed: 
            self.publish(policy,public,topic,args)
            # push subtrees to their respective remote branches
            push_subtrees = config.get("subtrees", 'pushOnPublish').lower() == "true" or args["--pushSubtrees"]
            push_subtrees = push_subtrees and not args["--noPushSubtrees"]
            if push_subtrees:

                subtrees = config.get('subtrees','names').split(' ')
                for st in subtrees:
                    st_prefix = config.get('subtree-%s'% st,'prefix')
                    st_remote = subtree.parseSubtreeRemote(config.get('subtree-%s'% st,'remote'))
                    st_branchMappings = config.get('subtree-%s'% st,'topicPrefixMappings')
                    st_branch = grapeConfig.parseConfigPairList(st_branchMappings)[topic]
                    print("pushing subtree %s to %s (branch %s)..." % (st_prefix,st_remote,st_branch))
                    git.subtree("push --prefix=%s %s %s" % (st_prefix,st_remote,st_branch),quiet=quiet)



    def set_default_config(self,config): 
        try:
            config.add_section('workspace')
        except ConfigParser.DuplicateSectionError:
            pass
        try: 
            config.add_section('flow')
        except ConfigParser.DuplicateSectionError:
            pass
        try:
            config.add_section("subtrees")
        except ConfigParser.DuplicateSectionError:
            pass



        config.set('workspace','manageSubmodules','True')
        config.set('workspace','submoduleTopicPrefixMappings','?:develop')
        config.set('workspace','submodulePublishPolicy','?:merge')
        config.set('flow','publishPolicy','?:merge')
        config.set('subtrees','names','None')
        config.set('subtrees', 'pushOnPublish', "True")
        

