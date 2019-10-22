import logging
from vine import config_parser_global
from vine import grapeGit as git
from vine import utility
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.option import Option
from vine.vine_logging import log_wrapper


class UpdateSubproject(Option, WorkspaceDirHandler):
    """
        grape updateSubproject
        Updates an existing subproject from its host repository.

        Usage: grape-updateSubproject subtree --name=<name> --branch=<committish>

        Options:
        --name=<name>           The name of the subproject. Must match a [subtree-<name>]
                                section in .grapeconfig that has prefix and remote options defined.

        --branch=<committish>   The branch in the subtree's host repository whose state
                                you want in your repository.

    """

    def __init__(self):
        super(UpdateSubproject, self).__init__()
        self._section = "Project Management"
        self._key = "updateSubproject"

    def description(self):
        return "Updates a subproject (such as a subtree) from the subproject's host repository."

    @log_wrapper
    def execute(self, args):
        if args["subtree"]:
            self.updateSubtree(args)

    def updateSubtree(self, args):
        clean = utility.isWorkspaceClean(workspace_dir=self.workspace_dir)
        if not clean:
            logging.info("git-subtree requires a clean working tree before attempting a subtree update")
            return False
        name = args["--name"]
        branch = args["--branch"]
        config = config_parser_global.grapeConfig()
        subtreePrefix = config.get(f"subtree-{name}", "prefix")
        subtreeRemote = config.get(f"subtree-{name}", "remote")
        fullURL = git.parseSubprojectRemoteURL(
            subtreeRemote, execution_path=self.workspace_dir)
        doSquash = config.get(Option.SECTION_SUBTREES, "mergePolicy").strip().lower() == "squash"
        squashArg = "--squash" if doSquash else ""
        git.subtree(f"pull --prefix {subtreePrefix} {fullURL} {branch} " +
                    f"{squashArg}", execution_path=self.workspace_dir)

        return True

    def setDefaultConfig(self, config):
        # let addSubproject govern needed defaults
        pass
