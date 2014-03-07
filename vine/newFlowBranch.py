import option
import utility
import types
import grapeGit as git
import grapeMenu

class NewBranchOption(option.Option): 
    def __init__(self,topic,public): 
        self._key = topic
        self._section = "Gitflow Tasks"
        self._public = public

    def description(self):
        return "Create and switch to a %s branch off of %s" % (self._key,self._public)

    def createBranch(self,branchPoint, prefix):
        branch = utility.userInput("Enter new branch name")
        user = utility.getUserName()
        fullBranch = prefix+"/"+user+"/"+branch
        proceed = utility.userInput("About to create branch "+fullBranch+" off of "+branchPoint+".\nProceed? [y/n]",'y')
        if (proceed):
            git.checkout("-b %s %s " % (fullBranch,branchPoint))
            git.push("-u origin %s" % fullBranch)
        else:
            print("Branch not created")

    def execute(self,args): 
        grapeMenu.menu().applyMenuChoice('up',['up'])
        self.createBranch(self._public,self._key)

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
