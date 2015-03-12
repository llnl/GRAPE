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
        oldstdout = sys.stdout
        # make sure the output is captured so we can check the number of fetches that occur
        if testProjectScenario.debugging() or debugging:
           self.switchToHiddenOutput()
        grapeMenu.menu().applyMenuChoice("up", ["-v"])
        upoutput = "%s" % self.output.getvalue()

        # print out the captured output if we were debugging
        if testProjectScenario.debugging() or debugging:
            self.switchToStdout()
            print upoutput

        numberOfFetches = upoutput.count("Executing: git fetch origin")
        self.assertEqual(numberOfFetches, testProjectScenario.numExpectedFetches(),
                         "Unexpected number of fetches %d != %d" % (numberOfFetches, testProjectScenario.numExpectedFetches()))
        
        if testProjectScenario.debugging() or debugging:
            self.switchToHiddenOutput()

def createUpTester(): 
    # create a tester for all grapeProject scenarios in the testProjectScenarios module. 
    scenarioClasses = testProjectScenarios.find_subclasses(testProjectScenarios, testProjectScenarios.grapeProject)
    names = [cls.__name__ for cls in scenarioClasses]
    scenarios = [cls(n) for (cls,n) in zip(scenarioClasses, names)]
    gridTesting.gridifyTestClass(scenarios, GrapeUpTester, names)
    return GrapeUpTester

