
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


def find_subclasses(module, clazz):
    return [
        cls
            for name, cls in inspect.getmembers(module)
                if inspect.isclass(cls) and issubclass(cls, clazz) and not cls is clazz
    ]

class GrapeStatusTester(testGrape.TestGrape): 

    def gridtestGrapeStatus(self, testProjectScenario):
        if testProjectScenario.debugging():
            self.switchToStdout()
        testProjectScenario.reset(projectPrefix=self.defaultWorkingDirectory)
        os.chdir(testProjectScenario.getProjectDir())
        ret = self.menu.applyMenuChoice("status", ["--failIfInconsistent"])
        if testProjectScenario.isConsistent(): 
            self.assertTrue(ret, "status thought a consistent project was inconsistent")
        else:
            self.assertFalse(ret, "status thought an inconsistent project was consistent")
        
        if testProjectScenario.debugging():
            self.switchToHiddenOutput()

def createStatusTester(): 
    # create a tester for all grapeProject scenarios in the testProjectScenarios module. 
    scenarioClasses = find_subclasses(testProjectScenarios, testProjectScenarios.grapeProject)
    names = [cls.__name__ for cls in scenarioClasses]
    scenarios = [cls(n) for (cls,n) in zip(scenarioClasses, names)]
    gridTesting.gridifyTestClass(scenarios, GrapeStatusTester, names)
    return GrapeStatusTester
    