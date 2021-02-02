import os
from test import testGrape
from vine import grapeGit as git


class TestUnbundle(testGrape.TestGrape):

    # Sets up a new nested subproject
    @staticmethod
    def assertCanAddNewSubproject(testGrapeObject, *, execution_path):
        # Create new subproject
        git.clone(argstr='--mirror', source_repo=testGrapeObject.repo,
                  clone_repo=testGrapeObject.repos[1],
                  execution_path=testGrapeObject.repo)
        subproject_path = os.path.join('subs', 'subproject1')
        testGrapeObject.menu.applyMenuChoice(
            "addSubproject", ["--name=subproject1",
                              f"--prefix={subproject_path}", "--branch=master",
                              f"--url={testGrapeObject.repos[1]}",
                              "--nested", "--noverify"])
        subproject1path = os.path.join(testGrapeObject.repo, subproject_path)
        testGrapeObject.assertTrue(os.path.exists(subproject1path), "subproject1 does not exist")
        # check in a file
        testGrape.writeFile3(os.path.join(subproject1path, "f3"))
        git.add("f3", execution_path=subproject1path)
        git.commit("-m \"added f3\"", execution_path=subproject1path)
        testGrapeObject.subproject = subproject1path

        # push changes to origin
        git.push("origin master", execution_path=testGrapeObject.repo)
        git.push("origin master", execution_path=subproject1path)

    def test_unbundle_given_defaults(self):
        """Test 'unbundle' command."""
        # Set up repo with one nested subproject
        self.assertCanAddNewSubproject(self, execution_path=self.repo)

        # Run bundle/unbundle from the top-level directory.
        # This ensures that unbundle will fail if glob is run from
        # the wrong directory.
        old_dir = os.getcwd()
        os.chdir(self.repo)
        # Bundle the repos
        result = self.menu.applyMenuChoice("bundle")
        self.assertTrue(result, "Failed 'bundle' command in unbundle test.")
        # Unbundle the repos
        result = self.menu.applyMenuChoice("unbundle")
        self.assertTrue(result, "Failed 'unbundle' command in unbundle test.")
        contents = self.get_output()
        self.assertNotIn("WARNING", contents,
                         f"GRAPE ISSUED A WARNING DURING UNBUNDLE\n{contents}")
        # Return to previous directory
        os.chdir(old_dir)


if __name__ == "__main__":
    import unittest
    unittest.main()
