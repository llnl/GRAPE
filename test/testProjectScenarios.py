import gridTesting
from testGrape import *


def find_subclasses(module, clazz):
    return [
        cls
            for name, cls in inspect.getmembers(module)
                if inspect.isclass(cls) and issubclass(cls, clazz) and not cls is clazz
    ]

class grapeProject(gridTesting.ResettableProject): 
    def __init__(self, path):
        super(grapeProject, self).__init__(path)
        self._debugging = False
        self._publicBranchesValid = False
        self._branchModelConsistent = False
        self._numExpectedFetches = 2

    def isConsistent(self): 
        return self._publicBranchesValid and self._branchModelConsistent
    
    def arePublicBranchesValid(self):
        return self._publicBranchesValid
    
    def isStateConsistentWithBranchModel(self):
        return self._branchModelConsistent
    
    def numExpectedFetches(self):
        return self._numExpectedFetches
    
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
        
        self._publicBranchesValid = True
        self._branchModelConsistent = True


class repoWithLocalGitflowBranches(singleRepo):
    def __init__(self, path): 
        super(repoWithLocalGitflowBranches, self).__init__(path)
        self.addCommands([
            (git.branch, "release master"),
            (git.branch, "develop master")
            ])
        
        self._publicBranchesValid = True
        self._branchModelConsistent = True

        
class repoWithLocalAndOriginGitflowBranches(repoWithLocalGitflowBranches):
    def __init__(self,path): 
        super(repoWithLocalAndOriginGitflowBranches, self).__init__(path)
        self.addCommands([(git.push, "origin --all")])
        self._publicBranchesValid = True
        self._branchModelConsistent = True
        
    
class singleRepoWithMissingLocalPublicBranches(repoWithLocalAndOriginGitflowBranches): 
    def __init__(self,path): 
        super(singleRepoWithMissingLocalPublicBranches, self).__init__(path)
        
        self.addCommands([
            (git.checkout, "-b feature/user/f1"),
            (git.branch, "-D master")
        ])
        
        self._publicBranchesValid = True
        self._branchModelConsistent = True
        

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
                                            "--noverify"],
                                            None,
                                            ["-v"] )),
                          (git.commit, "-m \"added submodule1\""),
                          (git.push, "origin --all")])
        self._publicBranchesValid = True
        self._branchModelConsistent = True
        
        
class WorkspaceWithSubmoduleOnDevelop(validRepoWithSubmodule):
    def __init__(self,path):
        super(WorkspaceWithSubmoduleOnDevelop, self).__init__(path)
        self.addCommands([
                           (os.chdir, "submodule1"),
                           (git.checkout, "develop"),
                           self.cdToProjectDirCmd(),
                         ])
        # outer on public branch means expect submodule on master
        self._publicBranchesValid = True
        self._branchModelConsistent = False
        
        
class WorkspaceOnDevelopSubmoduleOnDevelop(WorkspaceWithSubmoduleOnDevelop):
    def __init__(self, path):
        super(WorkspaceOnDevelopSubmoduleOnDevelop,self).__init__(path)
        self.addCommands([(git.checkout,"-B develop master"), 
                          ])
        # outer on public branch means we expect submodule on master
        self._publicBranchesValid = True
        self._branchModelConsistent = False
        
class WorkspaceOnTopicSubmoduleOnMaster(validRepoWithSubmodule):
    def __init__(self, path):
        super(WorkspaceOnTopicSubmoduleOnMaster, self).__init__(path)
        self.addCommands([(git.checkout, "-b topicBranch")])
        # outer on topic branch means we expect submodule on topic branch
        self._publicBranchesValid = True
        self._branchModelConsistent = False
        
class WorkspaceOnTopicSubmoduleOnTopic(WorkspaceOnTopicSubmoduleOnMaster):
    def __init__(self, path):
        super(WorkspaceOnTopicSubmoduleOnTopic, self).__init__(path)
        self.addCommands([(os.chdir,"submodule1"),
                          (git.checkout,"-b topicBranch")])
        # now both are on topicBranch
        self._publicBranchesValid = True
        self._branchModelConsistent= True
        
class WorkspaceOnTopicSubmoduleOnTopicTwoClients(WorkspaceOnTopicSubmoduleOnTopic):
    def __init__(self, path):
        super(WorkspaceOnTopicSubmoduleOnTopicTwoClients, self).__init__(path)
        self.secondProjectDir = self.projectDir + "2"
        if os.path.exists(self.secondProjectDir):
            print "Path (%s) already exists, so it cannot be used by a new ResettableProject." % self.secondProjectDir
            sys.exit(1)

        self.addCommands([(git.clone, lambda : "--recursive %s %s" % (self.getOriginDir(), self.getSecondProjectDir())), 
                          (os.chdir, lambda : self.getSecondProjectDir()),
                          (os.chdir,"submodule1"),
                          (git.checkout, "master"),
                          (writeFile1, "f2"),
                          (git.add,"f2"),
                          (git.commit, "-m \"added a second file to submodule\""),
                          (git.push, "origin master"),
                          (os.chdir, lambda : self.getSecondProjectDir()),
                          (git.checkout, "master"),
                          # We have to pull here because the submodule repo is the same as the original one
                          (git.pull, "origin"),
                          (git.add,"submodule1"),
                          (git.commit, "-m \"update gitlink\""),
                          (git.push, "origin master"),
                          self.cdToProjectDirCmd()
                         ])
        # now both are on topicBranch, but master is behind in both
        self._publicBranchesValid = True
        self._branchModelConsistent= True
        
    def getSecondProjectDir(self): 
        return os.path.abspath(os.path.join(self.projectPrefix,self.secondProjectDir))
    def tearDown(self): 
        super(WorkspaceOnTopicSubmoduleOnTopicTwoClients, self).tearDown()
        secondProjectDir = self.getSecondProjectDir()
        if os.path.exists(secondProjectDir) and os.path.isdir(secondProjectDir):
            os.chdir(os.path.abspath(os.path.join(secondProjectDir,"..")))
            shutil.rmtree(secondProjectDir, ignore_errors=True)
        
class WorkspaceWithDetachedSubmodule(validRepoWithSubmodule):
    def __init__(self, path):
        super(WorkspaceWithDetachedSubmodule, self).__init__(path)
        self.addCommands([(os.chdir,"submodule1"),
                          (git.checkout, "--detach")])
        # detached submodule is a bad place to be
        self._publicBranchesValid = True
        self._branchModelConsistent = False
        self._numExpectedFetches = 2
        
class ValidRepoWithNestedSubproject(repoWithLocalAndOriginGitflowBranches):
    def __init__(self,path):
        super(ValidRepoWithNestedSubproject, self).__init__(path)
        self.addCommands([(grapeMenu.menu().applyMenuChoice,
                         lambda: ("addSubproject", ["--name=subproject1",
                                            "--prefix=subproject1",
                                            "--url=%s" % self.getOriginDir(),
                                            "--branch=master", 
                                            "--nested", 
                                            "--noverify"], None, 
                                            ["-v"] ))])
        self._publicBranchesValid = True
        self._branchModelConsistent = True
        # there should be one fetch for the outer level master and one for the nested master
        self._numExpectedFetches = 2
        
class WorkspaceWithNestedOnDevelop(ValidRepoWithNestedSubproject):
    def __init__(self,path):
        super(WorkspaceWithNestedOnDevelop, self).__init__(path)
        self.addCommands([
                           (os.chdir, "subproject1"),
                           (git.checkout, "develop"),
                           self.cdToProjectDirCmd(),
                         ])
        # outer on public branch means expect submodule on master
        self._publicBranchesValid = True
        self._branchModelConsistent = False
        
        
