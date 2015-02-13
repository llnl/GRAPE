import os
import ConfigParser
import grapeConfig
import option
import utility
import grapeGit as git

"""        
                    
        --branch=<committish>  """
class UpdateSubproject(option.Option):
    """
        grape updateSubproject
        Updates an existing subproject from its host repository.  
        
        Usage: grape-updateSubproject subtree --name=<name> --branch=<committish>

        Options:
        --name=<name>  The name of the subproject. Must match a [subtree-<name>] section in .grapeconfig
                       that has prefix and remote options defined. 
        
        --branch=<b>   The branch in the subtree's host repository whose state you want in your 
                       repository.

    """
    
    def __init__(self):
        super(UpdateSubproject, self).__init__()
        self._section = "Project Management"
        self._key = "updateSubproject"
        
    def description(self):
        return "Updates a subproject (such as  a subtree) from the subproject's host repository."
    
    def execute(self, args):
        if args["subtree"]:
            self.updateSubtree(args)
        
    def updateSubtree(self, args):
        name = args["--name"]
        branch = args["--branch"]
        config = grapeConfig.grapeConfig()
        subtreePrefix = config.get("subtree-%s" % name, "prefix")
        subtreeRemote = config.get("subtree-%s" % name, "remote")
        doSquash = config.get("subtrees", "mergePolicy").strip().lower() == "squash"
        squashArg = "--squash" if doSquash else ""
        git.subtree("pull --prefix %s %s %s %s" %
                    (subtreePrefix, subtreeRemote, branch, squashArg))
        
    def setDefaultConfig(self, config):
        # let addSubproject govern needed defaults
        pass