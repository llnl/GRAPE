import os
from vine.config_parser_base import GrapeConfigParserBase
from vine.command_path_handler import CommandPathHandler


class GrapeConfigParserWorkspace(GrapeConfigParserBase):

    def __init__(self, workspaceDir, configString=None):
        # Imported here to avoid circular dependencies
        from vine import grapeMenu

        super(GrapeConfigParserWorkspace, self).__init__(
            workspaceDir=workspaceDir, configString=configString)
        menu = grapeMenu.menu()
        menu.set_command_path(workspaceDir)
        menu.setDefaultConfig(self)
        workspaceDir = self.__verify_workspace_dir(workspaceDir)
        self.read(os.path.join(workspaceDir, self.GRAPE_CONFIG))

    def __verify_workspace_dir(self, workspace_dir):
        tmp_handler = CommandPathHandler()
        tmp_handler.command_path = workspace_dir
        return tmp_handler.workspace_dir
