import glob
import os
import shutil
from test import testGrape
from unittest.mock import patch
from vine import grapeGit as git
from vine import grapeMenu


class TestUnbundle(testGrape.TestGrape):

    def setupSubproject(self):
        # Create new subproject
        git.clone(argstr='--mirror', source_repo=self.repo,
                  clone_repo=self.repos[1],
                  execution_path=self.repo)
        subproject_path = 'subproject1'
        self.menu.applyMenuChoice(
            "addSubproject", ["--name=subproject1",
                              f"--prefix={subproject_path}", "--branch=master",
                              f"--url={self.repos[1]}",
                              "--nested", "--noverify"])

        subproject1path = os.path.join(self.repo, subproject_path)
        self.assertTrue(os.path.exists(subproject1path), "subproject1 does not exist")
        # check in a file in subproject
        testGrape.writeFile3(os.path.join(subproject1path, "f3"))
        git.add("f3", execution_path=subproject1path)
        git.commit("-m \"added f3\"", execution_path=subproject1path)
        self.subproject = subproject1path
        # push changes to origin
        git.push("origin master", execution_path=self.repo)
        git.push("origin master", execution_path=self.subproject)

    @patch('vine.utility.userInput')
    def testUnbundleWithSubproject(self, mock_userInput):
        """Test 'unbundle' command."""
        # Set up nested subproject
        self.setupSubproject()

        # Save unmodified repos
        temp_repo = os.path.join(self.defaultWorkingDirectory, "temp_repo")
        temp_subproject = os.path.join(self.defaultWorkingDirectory, "temp_subproject")
        git.clone(source_repo=self.repo,
                  clone_repo=temp_repo,
                  execution_path=self.defaultWorkingDirectory)
        git.clone(source_repo=self.subproject,
                  clone_repo=temp_subproject,
                  execution_path=self.defaultWorkingDirectory)

        # Make some additional commits in each repo
        testGrape.writeFile3(os.path.join(self.repo, "extra"))
        git.add("extra", execution_path=self.repo)
        git.commit("-m \"added extra\"", execution_path=self.repo)
        testGrape.writeFile3(os.path.join(self.subproject, "extrasub"))
        git.add("extrasub", execution_path=self.subproject)
        git.commit("-m \"added extrasub\"", execution_path=self.subproject)
        # push changes to origin
        git.push("origin master", execution_path=self.repo)
        git.push("origin master", execution_path=self.subproject)

        # Run bundle from the top-level repo to simulate typical usage.
        old_dir = os.getcwd()
        os.chdir(self.repo)
        # Bundle the repos
        result = self.menu.applyMenuChoice("bundle")
        self.assertTrue(result, "Failed 'bundle' command in unbundle smoke test.")

        # Check that the bundle files exist
        toplevelbundle = glob.glob(os.path.join(self.repo, "*.bundle"))
        self.assertTrue(toplevelbundle, "Bundle in top level repo missing.")
        subprojectbundle = glob.glob(os.path.join(self.subproject, "*.bundle"))
        self.assertTrue(subprojectbundle, "Bundle in subproject missing.")

        # Move the bundles to a safe place
        toplevelbundletemp = os.path.join(self.defaultWorkingDirectory, os.path.split(toplevelbundle[0])[1])
        subprojectbundletemp = os.path.join(self.defaultWorkingDirectory, os.path.split(subprojectbundle[0])[1])
        shutil.copyfile(toplevelbundle[0], toplevelbundletemp)
        shutil.copyfile(subprojectbundle[0], subprojectbundletemp)

        # Blow away the repos
        repo_origin = self.repo + '-origin'
        shutil.rmtree(self.repo)
        shutil.rmtree(repo_origin)
        shutil.rmtree(self.repos[1])

        # Clone from the unmodified versions of the repos
        git.clone(argstr='--mirror', source_repo=temp_repo,
                  clone_repo=repo_origin,
                  execution_path=self.defaultWorkingDirectory)
        git.clone(source_repo=repo_origin, clone_repo=self.repo,
                  execution_path=self.defaultWorkingDirectory)
        git.clone(source_repo=temp_subproject,
                  clone_repo=self.subproject,
                  execution_path=self.defaultWorkingDirectory)

        # Refresh directory, since we deleted and recreated it
        os.chdir(self.repo)

        # Activate the subproject
        mock_userInput.side_effect = ["a\n"]
        self.menu.applyMenuChoice("uv")

        # Copy the bundles back into place
        shutil.copyfile(toplevelbundletemp, toplevelbundle[0])
        shutil.copyfile(subprojectbundletemp, subprojectbundle[0])

        # Run unbundle from the top-level repo to simulate typical usage.
        result = self.menu.applyMenuChoice("unbundle")
        self.assertTrue(result, "Failed 'unbundle' command in unbundle smoke test.")
        contents = self.get_output()
        self.assertNotIn("WARNING", contents,
                         f"GRAPE ISSUED A WARNING DURING UNBUNDLE\n{contents}")

        # Return to previous directory
        os.chdir(old_dir)


if __name__ == "__main__":
    import unittest
    unittest.main()
