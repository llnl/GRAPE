import logging
import os
from unittest.mock import patch

from vine import clone
from vine import grapeGit as git


class CloneSmokeCase:
    """Low-cost clone coverage kept together as one broad-run shard."""

    @patch("vine.utility.userInput")
    def testClone(self, mock_userInput):
        with self.preserved_cwd():
            self.setUpConfig()
            args = [self.repo, self.repos[1], "--recursive"]
            mock_userInput.side_effect = ["\n", "\n", "\n", "\n"]
            ret = self.menu.applyMenuChoice("clone", args)
            self.assertTrue(ret)

            contents = self.get_output()
            self.assertNotIn(contents, "Usage: grape-clone")
            self.assertNotIn(
                "WARNING",
                contents,
                f"GRAPE ISSUED A WARNING DURING A CLONE\n{contents}",
            )

            self.menu.set_workspace_dir(self.repos[1])
            remote = git.showRemote(execution_path=self.repos[1])
            self.assertIn(self.repo, remote)

    def testHelpMessage(self):
        with self.preserved_cwd():
            with self.captured_stdout() as doc_output:
                with self.assertRaises(SystemExit):
                    self.menu.applyMenuChoice("clone", ["--help"])
                self.assertIn(clone.Clone.__doc__.strip("\n"), doc_output.getvalue())

    @patch("vine.utility.userInput")
    def testClone02(self, mock_userInput):
        with self.preserved_cwd():
            with self.temp_clone_dir() as temp_dir:
                mock_userInput.side_effect = ["\n", "\n", "\n", "\n"]
                ret = self.menu.applyMenuChoice("clone", [self.repo, temp_dir])
                self.assertTrue(ret, "vine.clone returned failure")


class CloneSubmoduleCase:
    """Recursive clone flow that provisions a real Git submodule first."""

    def testRecursiveCloneWithSubmodule(self):
        with self.preserved_cwd():
            self.menu.set_workspace_dir(self.repo)
            git.clone(
                argstr="--mirror",
                source_repo=self.repo,
                clone_repo=self.repos[1],
                execution_path=self.defaultWorkingDirectory,
            )
            git.checkout("develop", execution_path=self.repo)
            git.submodule(f"add {self.repos[1]} submodule1", execution_path=self.repo)
            git.commit("-m \"added submodule1\"", execution_path=self.repo)

            with self.temp_clone_dir() as temp_dir:
                args = [self.repo, temp_dir, "--recursive"]
                with self.queue_user_input(["\n", "\n", "\n", "\n", "\n", "\n"]):
                    ret = self.menu.applyMenuChoice("clone", args)
                self.assertTrue(ret, "vine.clone returned failure")

                submodule_path = os.path.join(temp_dir, "submodule1")
                self.assertTrue(
                    os.path.exists(submodule_path),
                    "submodule1 does not exist in clone",
                )


class CloneNestedCase:
    """Recursive clone flow that exercises nested-subproject setup."""

    @patch("vine.utility.userInput")
    def testRecursiveCloneNestedSubproject(self, mock_userInput):
        with self.preserved_cwd():
            git.clone(
                argstr="--mirror",
                source_repo=self.repo,
                clone_repo=self.repos[1],
                execution_path=self.defaultWorkingDirectory,
            )
            self.menu.set_workspace_dir(self.repo)
            subproject_path = os.path.join("subs", "subproject1")
            self.menu.applyMenuChoice(
                "addSubproject",
                [
                    "--name=subproject1",
                    f"--prefix={subproject_path}",
                    "--branch=master",
                    f"--url={self.repos[1]}",
                    "--nested",
                    "--noverify",
                ],
            )
            self.menu.applyMenuChoice("commit", ["-m", "\"added subproject1\""])
            logging.info(git.log("--decorate", execution_path=self.repo))

            with self.temp_clone_dir() as temp_dir:
                args = [self.repo, temp_dir, "--recursive", "--allNested"]
                mock_userInput.side_effect = ["\n", "\n", "\n", "\n"]
                ret = self.menu.applyMenuChoice("clone", args)
                self.assertTrue(ret, "vine.clone returned failure")

                self.menu.set_workspace_dir(temp_dir)
                mock_userInput.side_effect = ["all\n"]
                ret = self.menu.applyMenuChoice("checkout", ["master", "--updateView"])
                self.assertTrue(ret, "vine.checkout master returned failure")
                logging.info(git.log("--decorate", execution_path=temp_dir))

                subproject_full_path = os.path.join(temp_dir, subproject_path)
                self.assertTrue(
                    os.path.exists(subproject_full_path),
                    "subproject1 does not exist in clone",
                )
