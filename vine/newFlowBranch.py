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

    Usage: grape-<type> [--start=<branch>] [--user=<username>] [--noverify] [--recurse | --norecurse] [<descr>] 

    Options:
    --user=<username>       The user developing this branch. Asks by default. 
    --start=<branch>        The start point for this branch. Default comes from .grapeconfig.flow.topicPrefixMappings. 
    --noverify              By default, grape will ask the user to verify the name and start point of the branch. 
                            This disables the verification. 
    --recurse               Create the branch in submodules. 
                            [default: .grapeconfig.workspace.manageSubmodules]
    --norecurse             Don't create the branch in submodules.
    
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

    @staticmethod
    def createBranch(branchPoint, prefix, user, descr, noverify):
        branch = descr if descr else utility.userInput("Enter one word description for branch:")
        user = user if user else utility.getUserName()
        fullBranch = prefix+"/"+user+"/"+branch
        proceed = noverify or utility.userInput("About to create branch "+fullBranch+" off of "+branchPoint +
                                                ".\nProceed? [y/n]", 'y')
        if proceed:
            git.checkout("-b %s %s " % (fullBranch, branchPoint))
            git.push("-u origin %s" % fullBranch)
        else:
            print("Branch not created")

        return branchPoint, prefix, user, branch

    def execute(self, args):
        grapeMenu.menu().applyMenuChoice('up', ['up'])
        start = args["--start"]
        recurse = grapeConfig.grapeConfig().get('workspace', 'manageSubmodules')
        if args["--recurse"]:
            recurse = True
        if args["--norecurse"]:
            recurse = False
        if not start: 
            start = self._public
        
        cwd = utility.workspaceDir()
        os.chdir(cwd)
        subArgs = self.createBranch(start, self._key, args['--user'], args['<descr>'], args['--noverify'])
        branchName = "%s/%s/%s" % (subArgs[1], subArgs[2], subArgs[3])
        # handle nested subprojects

        subprojectPrefixes = grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes()
        if subprojectPrefixes: 
            proceed = args["--noverify"] or utility.userInput("About to create the branch %s off of %s "
                                                                      "for all active nested subprojects.\n"
                                                                      "Proceed? [y/n]" % (branchName, start) , 'y')        
            if proceed:
                for sub in subprojectPrefixes: 
                    os.chdir(sub)
                    git.checkout(start)
                    grapeMenu.menu().applyMenuChoice('up', ['up', '--public=%s' % start])
                    self.createBranch(subArgs[0], subArgs[1], subArgs[2], subArgs[3], noverify=True)
        
        
        
        submodules = git.getActiveSubmodules()
        recurse = recurse and submodules
        if subArgs and recurse:
            proceed = args["--noverify"]
            submapping = grapeConfig.grapeConfig().getMapping('workspace', 'submoduleTopicPrefixMappings')
            submodulePublic = None
            try:
                submodulePublic = submapping[self._key]
            except KeyError:
                utility.printMsg("ManageSubmodules is enabled but.grapeconfig.workspace.submodueTopicPrefixMappings "
                                 "does not have a default value. Skipping branch creation for submodules.")
                proceed = False

            proceed = proceed or utility.userInput("About to create the branch " + branchName + " off of "
                                                   + submodulePublic +
                                                   " for all submodules.\nProceed? [y/n]", 'y')
            if proceed:
                for sub in submodules: 
                    os.chdir(os.path.join(cwd, sub))
                    git.checkout(submodulePublic)
                    grapeMenu.menu().applyMenuChoice('up', ['up', '--public=%s' % submodulePublic])
                    self.createBranch(submodulePublic, self._key, subArgs[2], subArgs[3], True)

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
