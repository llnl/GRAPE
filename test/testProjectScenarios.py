
import gridTesting
from testGrape import *


class grapeProject(gridTesting.ResettableProject): 
    def __init__(self, path):
        super(grapeProject, self).__init__(path)
        self._consistent = True

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
        
class singleRepoWithMissingPublicBranches(singleRepo): 
    def __init__(self,path): 
        super(singleRepoWithMissingPublicBranches, self).__init__(path)
        
        self.addCommands([
            (git.checkout, "-b feature/user/f1"),
            (git.branch, "-D master")
        ])
        
        self._consistent = False