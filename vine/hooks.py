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
        os.chdir(os.path.join(git.baseDir(),".git","hooks"))
        hooks = [#"commit-msg",
                "pre-commit",
                "pre-push",
                "pre-rebase",
                "post-commit"]
        for h in hooks: 
            with open(h,'w') as f: 
                f.write("#!/bin/sh\n")
                grapeCmd = utility.getGrapeExec()
                f.write("%s %s \"$@\" \n" % (grapeCmd,h+"-hook"))
        return True

#option that is called by the grape installed git post-commit hook
class PostCommit(option.Option): 
    def __init__(self):
        self._key = "post-commit-hook"
        self._section = "Hooks"

    def description(self): 
        return "Runs the grape post-commit hook."

    def execute(self):
        cfg = grapeConfig.grapeConfig()
        autoPush = cfg.get('post-commit','autopush')
        if autoPush.lower().strip() != "false": 
            git.push("origin HEAD")
        return True

    def setDefaultConfig(self,config):
        try: 
            config.add_section('post-commit')
        except ConfigParser.DuplicateSectionError:
            pass
        config.set('post-commit','autopush','False')

#option that is called by the grape installed git pre-commit hook
class PreCommit(option.Option): 
    def __init__(self):
        self._key = "pre-commit-hook"
        self._section = "Hooks"

    def description(self): 
        return "Runs the grape pre-commit hook."

    def execute(self):
        return True

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

    def execute(self):
        return True

    def setDefaultConfig(self,config):
        try: 
            config.add_section('pre-push')
        except ConfigParser.DuplicateSectionError:
            pass
       # config.set('post-commit','autopush','False')

#option that is called by the grape installed git pre-rebase hook
class PreRebase(option.Option): 
    def __init__(self):
        self._key = "pre-rebase-hook"
        self._section = "Hooks"

    def description(self): 
        return "Runs the grape pre-rebase hook."

    def execute(self):
        return True

    def setDefaultConfig(self,config):
        try: 
            config.add_section('pre-rebase')
        except ConfigParser.DuplicateSectionError:
            pass
       # config.set('post-commit','autopush','False')


