import os

from test import testGrape
from vine import config_parser_base
from vine import grapeGit as git
from vine import grapeMenu
from vine.option import Option


class NestedSubprojectTestBase(testGrape.TestGrape):
    """Shared helpers for the split nested-subproject suites."""

    @staticmethod
    def assertCanAddSecondSubproject(test_case, *, execution_path):
        subproject_path = os.path.join("subs", "subproject2")
        test_case.menu.applyMenuChoice(
            "addSubproject",
            [
                "--name=subproject2",
                f"--prefix={subproject_path}",
                "--branch=master",
                f"--url={test_case.repos[1]}",
                "--nested",
                "--noverify",
            ],
        )
        subproject2_path = os.path.join(test_case.repo, subproject_path)
        test_case.assertTrue(os.path.exists(subproject2_path), "subproject2 does not exist")
        base_dir = os.path.split(git.baseDir(execution_path=subproject2_path))[-1]
        sub_dir = os.path.split(subproject2_path)[-1]
        test_case.assertEqual(
            base_dir,
            sub_dir,
            f"subproject2's git repo is {base_dir}, not {sub_dir}",
        )
        test_case.subproject2 = subproject2_path

    @staticmethod
    def assertCanRemoveFirstSubproject(test_case, *, execution_path):
        grape_config = config_parser_base.GrapeConfigParserBase(execution_path)
        all_subprojects = grape_config.getAllNestedSubprojects()
        test_case.assertTrue("subproject1" in all_subprojects, "subproject1 not in grapeconfig")
        all_subprojects.remove("subproject1")
        grape_config.set(Option.SECTION_NESTED_PROJECTS, "names", " ".join(all_subprojects))
        grape_config.remove_section("nested-subproject1")
        with open(os.path.join(execution_path, ".grapeconfig"), "w") as handle:
            grape_config.write(handle)
        git.add(".grapeconfig", execution_path=execution_path)
        git.commit("-m \"removed subproject1\"", execution_path=execution_path)

    def switchToMaster(self):
        self.menu.applyMenuChoice("checkout", ["master"])

    def resetMenu(self, workspace_dir):
        """Rebuild the singleton menu after switching workspaces mid-test."""
        grapeMenu._resetMenu()
        self.menu = grapeMenu.menu(workspace_dir)
