import os
import inspect
import sys
import StringIO

import testGrape
import testProjectScenarios
import gridTesting

curPath = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
if not curPath in sys.path:
    sys.path.insert(0, curPath)
grapePath = os.path.join(curPath, "..")
if grapePath not in sys.path:
    sys.path.insert(0, grapePath)

from vine import grapeMenu  
from vine import grapeGit as git

class GrapeUpTester(testGrape.TestGrape): 

    def gridtestGrapeUp(self, testProjectScenario):
        
        debugging = False
        #if testProjectScenario.debugging() or debugging:
        #     self.switchToStdout()
        #oldstdout = sys.stdout
        os.chdir(testProjectScenario.getProjectDir())
        # make sure the output is captured so we can check the number of fetches that occur

        ret = grapeMenu.menu().applyMenuChoice("up", args=None, option_args=None, globalArgs=['-v'])
        self.assertTrue(ret, "up failed to run")
        # NOTE THAT THIS WILL FAIL IN DEBUG MODE (debugging set to True)
        #upoutput = "%s" % self.output.getvalue()
        #print upoutput.split('\n')
        #numberOfFetches = 0
        #for l in upoutput.split('\n'): 
        #    if "git fetch origin" in l and "Executing" in l:
        #        numberOfFetches += 1
        #self.assertEqual(numberOfFetches, testProjectScenario.numExpectedFetches(),
        #                 "Unexpected number of fetches %d != %d\n%s" % (numberOfFetches, testProjectScenario.numExpectedFetches(),upoutput))
        
        #if testProjectScenario.debugging() or debugging:
        #    self.switchToHiddenOutput()

def createUpTester(): 
    # create a tester for all grapeProject scenarios in the testProjectScenarios module. 
    scenarioClasses = testProjectScenarios.find_subclasses(testProjectScenarios, testProjectScenarios.grapeProject)
    names = [cls.__name__ for cls in scenarioClasses]
    scenarios = [cls(n) for (cls,n) in zip(scenarioClasses, names)]
    gridTesting.gridifyTestClass(scenarios, GrapeUpTester, names)
    return GrapeUpTester

