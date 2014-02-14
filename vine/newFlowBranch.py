import option
import utility
import types
import grapeGit as git

class NewBranchOption(option.Option): 
    def __init__(self,topic,public): 
        self._key = topic
        self._section = "Gitflow Tasks"
        self._public = public

    def description(self):
        return "Create and switch to a %s branch off of %s" % (self._key,self._public)

    def execute(self,args): 
        git.fetch("origin %s:%s" % (self._public, self._public))
        utility.createBranch(self._public,self._key)

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
