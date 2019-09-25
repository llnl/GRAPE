import os
import sys
from test import testGrape
from vine import grape_errors
from vine import grapeMenu
from vine import grapeGit as git
from vine import config_parser_global
from vine.option import Option


class TestVersion(testGrape.TestGrape):
    def testMinorTick(self):
        os.chdir(self.repo)
        # test initialization of grape managed versioning
        menu = grapeMenu.menu(workspace_dir=self.defaultWorkingDirectory)
        try:
#            self.assertEqual(grapeConfig.grapeConfig().get("versioning", "updateTag").lower(), "true")
            ret = menu.applyMenuChoice("version", ["init","v0.1.0", "--file=.grapeversion"])
            self.assertTrue(ret, "grape version init v0.1.0 returned False\n" +
                                 f"{self.get_output()}")
            self.assertEqual(git.describe("--abbrev=0"), "v0.1.0")

            # test to make sure ticking the version works
            ret = menu.applyMenuChoice("version", ["tick", "--minor"])
            self.assertTrue(ret, "grape version tick returned False")
            self.assertEqual(git.describe(), "v0.2.0")
        except SystemExit:
            self.fail(f"Unexpected SystemExit\n{self.get_output()}")
        except grape_errors.GrapeGitError as e:
            self.fail(f"Uncaught GrapeGit error: {e.gitOutput}")

    def testMajorTick(self):
        os.chdir(self.repo)
        menu = grapeMenu.menu(workspace_dir=self.defaultWorkingDirectory)
        try:

            ret = menu.applyMenuChoice("version", ["init","v0.1.0", "--file=.grapeversion"])
            self.assertTrue(ret, "grape version init v0.1.0 returned False\n" +
                                 f"{self.get_output()}")
            self.assertEqual(git.describe("--abbrev=0"), "v0.1.0")

            # test to make sure ticking the version works
            ret = menu.applyMenuChoice("version", ["tick", "--major"])
            self.assertTrue(ret, "grape version tick returned False")
            self.assertEqual(git.describe(), "v1.0.0")

            # test a minor tick with no tag update
            ret = menu.applyMenuChoice("version", ["tick", "--minor", "--notag"])
            self.assertEqual(git.describe("--abbrev=0"), "v1.0.0")

            ret = menu.applyMenuChoice("version", ["tick", "--minor"])
            self.assertEqual(git.describe(), "v1.2.0")

            ret = menu.applyMenuChoice("version", ["tick", "--major"])
            self.assertEqual(git.describe(), "v2.0.0")

            #test overiding default tag behavior
            config = config_parser_global.grapeConfig()
            config.set(Option.SECTION_VERSIONING, "updateTag", "False")
            ret = menu.applyMenuChoice("version", ["tick", "--slot=3"])
            self.assertEqual(git.describe("--abbrev=0"), "v2.0.0")
            ret = menu.applyMenuChoice("version", ["tick", "--slot=3", "--tag"])
            self.assertEqual(git.describe(), "v2.0.2")

            # test auto extension of version number
            menu.applyMenuChoice("version", ["tick", "--slot=4", "--tag"])
            self.assertEqual(git.describe(), "v2.0.2.1")


        except SystemExit:
            self.fail(f"Unexpected SystemExit\n{self.get_output()}")
        except grape_errors.GrapeGitError as e:
            self.fail(f"Uncaught GrapeGitError: {e.gitOutput}")
