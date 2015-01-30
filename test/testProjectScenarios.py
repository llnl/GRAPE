
import gridTesting
from testGrape import *


class grapeProject(gridTesting.ResettableProject): 
    def __init__(self, path):
        super(grapeProject, self).__init__(path)
        self._consistent = False

    def isConsistent(self): 
        return self._consistent
    
class singleRepo(grapeProject): 
    def __init__(self, path): 
        super(singleRepo, self).__init__(path)
        
        self.addCommands([
            (writeFile1, "f1"),
            (git.add,"f1"),
            (git.commit, "-m \"added a single file\"")
        ])
        
        self._consistent = False

class repoWithLocalGitflowBranches(singleRepo):
    def __init__(self, path): 
        super(repoWithLocalGitflowBranches, self).__init__(path)
        self.addCommands([
            (git.branch, "release master"),
            (git.branch, "develop master")
            ])
        
        self._consistent = False
        
class repoWithLocalAndOriginGitflowBranches(repoWithLocalGitflowBranches):
    def __init__(self,path): 
        super(repoWithLocalAndOriginGitflowBranches, self).__init__(path)
        self.addCommands([(git.push, "origin --all")])
        self._consistent = True
    
class singleRepoWithMissingLocalPublicBranches(repoWithLocalAndOriginGitflowBranches): 
    def __init__(self,path): 
        super(singleRepoWithMissingLocalPublicBranches, self).__init__(path)
        
        self.addCommands([
            (git.checkout, "-b feature/user/f1"),
            (git.branch, "-D master")
        ])
        
        self._consistent = False
        
