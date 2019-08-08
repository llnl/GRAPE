import logging
import os
from vine import config_parser_user
from vine import grape_errors
from vine import grapeGit as git
from vine import utility
from vine import vine_logging
from vine.option import Option
from vine.vine_logging import log_wrapper


class Commit(Option):
    """
    Usage: grape-commit [-m <message>] [-a | <filetree>]

    Options:
    -m <message>    The commit message.
    -a              Commit modified files that have not been staged.


    Arguments:
    <filetree> The relative path of files to include in this commit.

    """
    def __init__(self):
        super(Commit,self).__init__()
        self._key = "commit"
        self._section = "Workspace"

    def description(self):
        return "runs git commit in all projects in this workspace"

    def commit(self, commitargs, repo):
        try:
            git.commit(commitargs)
            return True
        except grape_errors.GrapeGitError as e:
            logging.error(f"Commit in {repo} failed. Perhaps there were no " +
                          "staged changes? Use -a to commit all modified files.")
            return False

    @log_wrapper
    def execute(self, args):
        commitargs = ""
        if args['-a']:
            commitargs = commitargs +  " -a"
        elif args["<filetree>"]:
            commitargs = commitargs + f" {args['<filetree>']}"
        if not args['-m']:
            args["-m"] = utility.userInput("Please enter commit message:")
        commitargs += f" -m \"{args['-m']}\""

        wsDir = utility.workspaceDir()
        os.chdir(wsDir)

        submodules = [(True, x ) for x in git.getModifiedSubmodules(utility.workspaceDir())]
        subprojects = [(False, x) for x in config_parser_user.getAllActiveNestedSubprojectPrefixes()]
        for stage, sub in submodules + subprojects:
            os.chdir(os.path.join(wsDir, sub))
            subStatus = git.status("--porcelain -uno")
            if subStatus:
                logging.info(f"Committing in {sub}...")
                if self.commit(commitargs, sub) and stage:
                    os.chdir(wsDir)
                    logging.info(f"Staging committed change in {sub}...")
                    git.add(sub)

        os.chdir(wsDir)
        if submodules or git.status("--porcelain"):
            logging.info("Performing commit in outer level project...")
            self.commit(commitargs, wsDir)
        return True

    def setDefaultConfig(self,config):
        pass
