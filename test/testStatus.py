
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




class GrapeStatusTester(testGrape.TestGrape): 

    def gridtestGrapeStatus(self, testProjectScenario): 
        #self.switchToStdout()
        testProjectScenario.reset(projectPrefix=self.defaultWorkingDirectory)
        os.chdir(testProjectScenario.getProjectDir())
        ret = self.menu.applyMenuChoice("status", ["--failIfInconsistent"])
        if testProjectScenario.isConsistent(): 
            self.assertTrue(ret, "status thought a consistent project was inconsistent")
        else:
            self.assertFalse(ret, "status thought an inconsistent project was consistent")
        #self.switchToHiddenOutput()

def createStatusTester(): 
    scenarios = [testProjectScenarios.singleRepo("singleRepo"),
                 testProjectScenarios.singleRepoWithMissingPublicBranches("singleRepoWithMissingPublicBranches")]
    gridTesting.gridifyTestClass(scenarios, GrapeStatusTester)
    return GrapeStatusTester
    