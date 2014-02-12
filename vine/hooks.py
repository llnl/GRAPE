import option, sys, utility, os
import grapeGit as git
import ConfigParser
import grapeConfig

#option that installs wrapper calls to grape as git hooks in this repo. 
class InstallHooks(option.Option):
    def __init__(self):
        self._key = "installHooks"
        self._section = "Hooks"

    def description(self):
        return "Installs grape as your hook manager for this repo. (May overwrite existing hooks you have installed in this repo)"

    def execute(self):
        os.chdir(os.path.join(git.gitDir(),"hooks"))
        hooks = [#"commit-msg",
                "pre-commit",
                "pre-push",
                "pre-rebase",
                "post-commit",
                "post-rebase",
                "post-merge"]
        for h in hooks: 
            with open(h,'w') as f: 
                f.write("#!/bin/sh\n")
                grapeCmd = utility.getGrapeExec()
                f.write("%s %s \"$@\" \n" % (grapeCmd,h+"-hook"))
            os.chmod(h,0755)
        return True

#option that is called by the grape installed git post-commit hook
class PostCommit(option.Option): 
    def __init__(self):
        self._key = "post-commit-hook"
        self._section = "Hooks"

    def description(self): 
        return "Runs the grape post-commit hook."

    def execute(self,args):
        cfg = grapeConfig.grapeConfig()
        
        #applies the autoPush hook
        autoPush = cfg.get('post-commit','autopush')
        if autoPush.lower().strip() != "false": 
            #try:
            print "calling git.push"
            git.push("-u origin HEAD")
            print "out of git push"
            #except:
            #pass
            autoPush = True
        else:
            autoPush = False
        #applies the cascade hook
        print "looking up cascades info"
        cascades = cfg.get('post-commit','cascade').split(' ')
        if cascades[0].strip().lower() != "none": 
            cascadeDict = {}
            for c in cascades:
                clist = c.split(':')
                cascadeDict[clist[0]] = clist[1]
            currentBranch = git.currentBranch()
            while currentBranch in cascadeDict:
                source = currentBranch
                target = cascadeDict[source]
                fastForward = False
                print("GRAPE: Cascading commit from %s to %s..." % (source,target))
                if git.branchUpToDateWith(source,target): 
                    fastForward = True
                    print("GRAPE: should be a fastforward cascade...")
                git.checkout("%s" % target)
                git.merge("%s -m 'Cascade from %s to %s'" % (source,source,target))
                # we need to kick off the next one if it was a fast forward merge. 
                # otherwise, another post-commit hook should be called from the merge commit. 
                if fastForward:
                    if autoPush: 
                        git.push("origin %s" % target)
                    currentBranch = target
                else:
                    currentBranch = None
        exit(0)

    def setDefaultConfig(self,config):
        try: 
            config.add_section('post-commit')
        except ConfigParser.DuplicateSectionError:
            pass
        config.set('post-commit','autopush','False')
        config.set('post-commit','cascade','None')

#option that is called by the grape installed git pre-commit hook
class PreCommit(option.Option): 
    def __init__(self):
        self._key = "pre-commit-hook"
        self._section = "Hooks"

    def description(self): 
        return "Runs the grape pre-commit hook."

    def execute(self,args = None):
        exit(0)

    def setDefaultConfig(self,config):
        try: 
            config.add_section('pre-commit')
        except ConfigParser.DuplicateSectionError:
            pass
       # config.set('post-commit','autopush','False')

#option that is called by the grape installed git pre-push hook
class PrePush(option.Option): 
    def __init__(self):
        self._key = "pre-push-hook"
        self._section = "Hooks"

    def description(self): 
        return "Runs the grape pre-push hook."

    def execute(self,args=None):
        exit(0)

    def setDefaultConfig(self,config):
        try: 
            config.add_section('pre-push')
        except ConfigParser.DuplicateSectionError:
            pass
       # config.set('post-commit','autopush','False')

#option that is called by the grape installed git pre-rebase hook
class PostRebase(option.Option): 
    def __init__(self):
        self._key = "post-rebase-hook"
        self._section = "Hooks"

    def description(self): 
        return "Runs the grape post-rebase hook."

    def execute(self,args= None):
        cfg = grapeConfig.grapeConfig()
        updateSubmodule = cfg.get('post-rebase','submoduleUpdate')
        if updateSubmodule.lower() == 'true': 
            git.submodule("update --rebase")
        exit(0)

    def setDefaultConfig(self,config):
        try: 
            config.add_section('post-rebase')
        except ConfigParser.DuplicateSectionError:
            pass
        config.set('post-rebase','submoduleUpdate','False')


#option that is called by the grape installed git pre-merge hook
class PostMerge(option.Option): 
    def __init__(self):
        self._key = "post-merge-hook"
        self._section = "Hooks"

    def description(self): 
        return "Runs the grape post-merge hook."

    def execute(self,args= None):
        cfg = grapeConfig.grapeConfig()
        updateSubmodule = cfg.get('post-merge','submoduleUpdate')
        if updateSubmodule.lower() == 'true': 
            git.submodule("update --merge")
        exit(0)

    def setDefaultConfig(self,config):
        try: 
            config.add_section('post-merge')
        except ConfigParser.DuplicateSectionError:
            pass
        config.set('post-merge','submoduleUpdate','False')


#option that is called by the grape installed git pre-rebase hook
class PreRebase(option.Option): 
    def __init__(self):
        self._key = "pre-rebase-hook"
        self._section = "Hooks"

    def description(self): 
        return "Runs the grape pre-rebase hook."

    def execute(self,args= None):
        exit(0)

    def setDefaultConfig(self,config):
        try: 
            config.add_section('pre-rebase')
        except ConfigParser.DuplicateSectionError:
            pass
       # config.set('post-commit','autopush','False')



#option that is called by the grape installed git pre-checkout hook
class PostCheckout(option.Option): 
    def __init__(self):
        self._key = "post-checkout-hook"
        self._section = "Hooks"

    def description(self): 
        return "Runs the grape post-checkout hook."

    def execute(self,args= None):
        cfg = grapeConfig.grapeConfig()
        updateSubmodule = cfg.get('post-checkout','submoduleUpdate')
        if updateSubmodule.lower() == 'true': 
            git.submodule("update")
        exit(0)

    def setDefaultConfig(self,config):
        try: 
            config.add_section('post-checkout')
        except ConfigParser.DuplicateSectionError:
            pass
        config.set('post-checkout','submoduleUpdate','False')


