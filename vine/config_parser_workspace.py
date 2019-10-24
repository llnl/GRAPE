import os
from vine.config_parser_base import GrapeConfigParserBase
from vine.workspace_dir_handler import WorkspaceDirHandler


class GrapeConfigParserWorkspace(GrapeConfigParserBase):

    def __init__(self, workspaceDir, configString=None):
        # Imported here to avoid circular dependencies
        from vine import grapeMenu

        super(GrapeConfigParserWorkspace, self).__init__(
            workspaceDir=workspaceDir, configString=configString)
        menu = grapeMenu.menu(workspace_dir=workspaceDir)
        menu.setDefaultConfig(self)
        workspaceDir = menu.workspace_dir
        self.read(os.path.join(workspaceDir, self.GRAPE_CONFIG))
