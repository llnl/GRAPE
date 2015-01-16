
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




class GrapeStatusTester(): 
    def testGrapeStatus(self, testProjectScenario): 
        os.chdir(testProjectScenario.projectDir)
        ret = self.menu.applyMenuChoice("status", ["--failIfInconsistent"])
        if testProjectScenario.isConsistent(): 
            self.assertTrue(ret == 0, "status thought a consistent project was inconsistent")
        else:
            self.assertTrue(ret > 0, "status thought an inconsistent project was consistent")

def createStatusTester(rootPath): 
    scenarios = [testProjectScenarios.singleRepo(os.path.join(rootPath,"singleRepo")),
                 testProjectScenarios.singleRepoWithMissingPublicBranches, "singleRepoWithMissingPublicBranches"]
    return  gridTesting.createGridTestClass(scenarios, GrapeStatusTester, "Test Grape Status")
    