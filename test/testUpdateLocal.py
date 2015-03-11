import os
import inspect
import sys
import StringIO

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

class GrapeUpTester(testGrape.TestGrape): 

    def gridtestGrapeUp(self, testProjectScenario):
        debugging = False
        if testProjectScenario.debugging() or debugging:
            self.switchToStdout()
        os.chdir(testProjectScenario.getProjectDir())
        grapeMenu.menu().applyMenuChoice("up", ["-v"])
        # This currently does nothing!
        # We need to capture the output of up and count the fetches
        
        if testProjectScenario.debugging() or debugging:
            self.switchToHiddenOutput()

def createUpTester(): 
    scenarioClasses = [ testProjectScenarios.WorkspaceOnTopicSubmoduleOnTopicTwoClients ]
    names = [cls.__name__ for cls in scenarioClasses]
    scenarios = [cls(n) for (cls,n) in zip(scenarioClasses, names)]
    gridTesting.gridifyTestClass(scenarios, GrapeUpTester, names)
    return GrapeUpTester

