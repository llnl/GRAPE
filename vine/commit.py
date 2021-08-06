import logging
import os
from vine import config_parser_user
from vine import grape_errors
from vine import grapeGit as git
from vine import utility
from vine.option import Option
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.vine_logging import log_wrapper


class Commit(Option, WorkspaceDirHandler):
    """
    Usage: grape-commit [-m <message>] [-a | <filetree>...]

    Options:
    -m <message>    The commit message.
    -a              Commit modified files that have not been staged.


    Arguments:
    <filetree>... The relative paths of files to include in this commit.

    """
    def __init__(self):
        super(Commit, self).__init__()
        self._key = "commit"
        self._section = "Workspace"

    def description(self):
        return "runs git commit in all projects in this workspace"

    def commit(self, commitargs, repo):
        try:
            git.commit(commitargs, execution_path=repo)
            return True
        except grape_errors.GrapeGitError as e:
            logging.error(f"Commit in {repo} failed. Perhaps there were no " +
                          "staged changes? Use -a to commit all modified files.")
            return False

    @log_wrapper
    def execute(self, args):
        filetrees = None
        commitargs = ""
        if args['-a']:
            commitargs = commitargs +  " -a"
        else if args["<filetree>"]:
            filetrees = {os.path.abspath(x):False for x in args['<filetree>']}
        if not args['-m']:
            args["-m"] = utility.userInput("Please enter commit message:")

        commitargs += f" -m \"{args['-m']}\""

        submodules = [(True, x ) for x in git.getModifiedSubmodules(self.workspace_dir)]

        subprojects = [(False, x) for x in config_parser_user.getAllActiveNestedSubprojectPrefixes(workspaceDir=self.workspace_dir)]
        for stage, sub in submodules + subprojects:
            sub_path = os.path.join(self.workspace_dir, sub)
            if filetrees:
                for f in filetrees.keys():
                    relpath = os.path.relpath(f,sub_path)
                    if ".." not in relpath:
                        logging.info(f"Committing {relpath} in {sub}...")
                        self.commit(commitargs + f" {relpath}", sub_path)
                        filetrees[f] = True
                        if stage:
                            logging.info(f"Staging committed change in {sub}...")
                            git.add(sub, execution_path=self.workspace_dir)

            else:
                subStatus = git.status("--porcelain -uno", execution_path=sub_path)
                if subStatus:
                    logging.info(f"Committing in {sub}...")
                    if self.commit(commitargs, sub_path) and stage:
                        logging.info(f"Staging committed change in {sub}...")
                        git.add(sub, execution_path=self.workspace_dir)

        remaining_filetrees = ''
        if filetrees:
            remaining_filetrees = ' '.join([os.path.relpath(x,self.workspace_dir) for x in filetrees.keys() if not filetrees[x]])

        if submodules or git.status("--porcelain", execution_path=self.workspace_dir) or remaining_filetrees:

            logging.info(f"Committing {remaining_filetrees} in {self.workspace_dir} ...")
            self.commit(commitargs + ' ' + remaining_filetrees, self.workspace_dir)
        return True

    def setDefaultConfig(self,config):
        pass
