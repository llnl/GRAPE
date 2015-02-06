
import os
import inspect
import sys

import testGrape
import testProjectScenarios
import gridTesting

curPath = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
if not curPath in sys.path:
    sys.path.append(curPath)
grapePath = os.path.join(curPath, "..")
if grapePath not in sys.path:
    sys.path.append(grapePath)

from vine import grapeMenu  
from vine import grapeGit as git

def find_subclasses(module, clazz):
    return [
        cls
            for name, cls in inspect.getmembers(module)
                if inspect.isclass(cls) and issubclass(cls, clazz) and not cls is clazz
    ]

class GrapeStatusTester(testGrape.TestGrape): 

    def gridtestGrapeStatus(self, testProjectScenario):
        debugging = False
        if testProjectScenario.debugging() or debugging:
            self.switchToStdout()
        os.chdir(testProjectScenario.getProjectDir())
        self.assertTrue(self.menu.applyMenuChoice("status"), 
                        "status Failed when no flags requesting fail codes were used.")
        ret = self.menu.applyMenuChoice("status", ["--failIfInconsistent"])
        if testProjectScenario.isConsistent(): 
            self.assertTrue(ret, "status thought a consistent project was inconsistent")
        else:
            self.assertFalse(ret, "status thought an inconsistent project was consistent")
        
        if testProjectScenario.debugging() or debugging:
            self.switchToHiddenOutput()
            
    def gridtestGrapeCheckoutOfMasterFixesGrapeStatusBranchConsistency(self, testProjectScenario): 
        debugging = False
        if testProjectScenario.debugging() or debugging:
            self.switchToStdout()
        os.chdir(testProjectScenario.getProjectDir())
        ret = self.menu.applyMenuChoice("status", ["--failIfBranchesInconsistent"])
        if testProjectScenario.isStateConsistentWithBranchModel(): 
            self.assertTrue(ret, "grape thought consistent branch model repo was inconsistent")
        else:
            self.assertFalse(ret, "grape thought inconsistent branch model repo was consistent")
            self.menu.applyMenuChoice("checkout", ["master"])
            ret = self.menu.applyMenuChoice("status", ["--failIfBranchesInconsistent"])
            self.assertTrue(ret, "status not consistent after a grape checkout of master")

        
        if testProjectScenario.debugging() or debugging:
            self.switchToHiddenOutput()

def createStatusTester(): 
    # create a tester for all grapeProject scenarios in the testProjectScenarios module. 
    scenarioClasses = find_subclasses(testProjectScenarios, testProjectScenarios.grapeProject)
    names = [cls.__name__ for cls in scenarioClasses]
    scenarios = [cls(n) for (cls,n) in zip(scenarioClasses, names)]
    gridTesting.gridifyTestClass(scenarios, GrapeStatusTester, names)
    return GrapeStatusTester
    