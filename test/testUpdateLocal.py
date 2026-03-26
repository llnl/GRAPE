import os
import sys
from unittest.mock import patch
from test import gridTesting
from test import testGrape
from test import testProjectScenarios
from vine import updateLocal


class GrapeUpTester(testGrape.TestGrape):

    def gridtestGrapeUp(self, testProjectScenario):
        self.menu.set_workspace_dir(testProjectScenario.getProjectDir())
        ret = self.menu.applyMenuChoice("up", args=None, option_args=None)
        self.assertTrue(ret, "up failed to run")
        # NOTE The following counting of the number of fetches is incorrect
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


class TestUpdateLocalHelpers(testGrape.TestGrape):

    @patch("vine.updateLocal.checkout.applyMovedSubmodules")
    @patch("vine.updateLocal.checkout.parseGitModulesDiffOutput")
    def testApplyMovedSubmodulesAfterUpdateSucceeds(self, mock_parse,
                                                    mock_apply):
        def fill_moved_modules(current_sha, branch, added, removed, changed,
                               moved, *, workspace_dir):
            moved["old/sub"] = "new/sub"

        mock_parse.side_effect = fill_moved_modules
        mock_apply.return_value = ({"old/sub": "new/sub"}, {})

        ret = updateLocal.applyMovedSubmodulesAfterUpdate(
            "abc123", workspace_dir=self.repo)

        self.assertTrue(ret)
        mock_parse.assert_called_once()
        mock_apply.assert_called_once_with({"old/sub": "new/sub"},
                                           workspace_dir=self.repo)

    @patch("vine.updateLocal.checkout.applyMovedSubmodules")
    @patch("vine.updateLocal.checkout.parseGitModulesDiffOutput")
    def testApplyMovedSubmodulesAfterUpdateFails(self, mock_parse,
                                                 mock_apply):
        def fill_moved_modules(current_sha, branch, added, removed, changed,
                               moved, *, workspace_dir):
            moved["old/sub"] = "new/sub"

        mock_parse.side_effect = fill_moved_modules
        mock_apply.return_value = ({}, {"old/sub": "new/sub"})

        ret = updateLocal.applyMovedSubmodulesAfterUpdate(
            "abc123", workspace_dir=self.repo)

        self.assertFalse(ret)
        mock_parse.assert_called_once()

def createUpTester():
    # create a tester for all grapeProject scenarios in the testProjectScenarios module.
    scenarioClasses = testProjectScenarios.find_subclasses(testProjectScenarios, testProjectScenarios.grapeProject)
    names = [cls.__name__ for cls in scenarioClasses]
    scenarios = [cls(n) for (cls,n) in zip(scenarioClasses, names)]
    gridTesting.gridifyTestClass(scenarios, GrapeUpTester, names)
    return GrapeUpTester
