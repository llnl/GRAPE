
import gridTesting
from testGrape import *


class grapeProject(gridTesting.ResettableProject): 
    def __init__(self, path):
        super(grapeProject, self).__init__(path)
        self._consistent = False
        self._debugging = False

    def isConsistent(self): 
        return self._consistent
    
    def debugging(self):
        return self._debugging
    
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
        

# setting up subrojects
# default grapeconfig expects all submodules to be on master branch when on 
# public branch in workspace. 
class validRepoWithSubmodule(repoWithLocalAndOriginGitflowBranches): 
    def __init__(self,path):
        super(validRepoWithSubmodule, self).__init__(path)
        self.addCommands([(grapeMenu.menu().applyMenuChoice,
                         lambda: ("addSubproject", ["--name=submodule1",
                                            "--prefix=submodule1",
                                            "--url=%s" % self.getOriginDir(),
                                            "--branch=master", 
                                            "--submodule", 
                                            "--noverify",
                                            "-v"] )),
                          (git.commit, "-m \"added submodule1\"")])
        self._consistent = True
        
class WorkspaceWithSubmoduleOnDevelop(validRepoWithSubmodule):
    def __init__(self,path):
        super(WorkspaceWithSubmoduleOnDevelop, self).__init__(path)
        self.addCommands([
                           (os.chdir, "submodule1"),
                           (git.checkout, "develop"),
                           self.cdToProjectDirCmd(),
                         ])
        # outer on public branch means expect submodule on master
        self._consistent = False 
        
        
class WorkspaceOnDevelopSubmoduleOnDevelop(WorkspaceWithSubmoduleOnDevelop):
    def __init__(self, path):
        super(WorkspaceOnDevelopSubmoduleOnDevelop,self).__init__(path)
        self.addCommands([(git.checkout,"-B develop master"), 
                          ])
        # outer on public branch means we expect submodule on master
        self._consistent = False
        
class WorkspaceOnTopicSubmoduleOnMaster(validRepoWithSubmodule):
    def __init__(self, path):
        super(WorkspaceOnTopicSubmoduleOnMaster, self).__init__(path)
        self.addCommands([(git.checkout, "-b topicBranch")])
        # outer on topic branch means we expect submodule on topic branch
        self._consistent = False
        
class WorkspaceOnTopicSubmoduleOnTopic(WorkspaceOnTopicSubmoduleOnMaster):
    def __init__(self, path):
        super(WorkspaceOnTopicSubmoduleOnTopic, self).__init__(path)
        self.addCommands([(os.chdir,"submodule1"),
                          (git.checkout,"-b topicBranch")])
        # now both are on topicBranch
        self._consistent = True
        
class WorkspaceWithDetachedSubmodule(validRepoWithSubmodule):
    def __init__(self, path):
        super(WorkspaceWithDetachedSubmodule, self).__init__(path)
        self.addCommands([(os.chdir,"submodule1"),
                          (git.checkout, "--detach")])
        # detached submodule is a bad place to be
        self._consistent = False
        