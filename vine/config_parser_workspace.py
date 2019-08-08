import os
from vine import config_parser_base
from vine import utility


class GrapeConfigParserWorkspace(config_parser_base.GrapeConfigParserBase):

    def __init__(self, workspaceDir=None, configString=None):
        # Imported here to avoid circular dependencies
        from vine import grapeMenu

        super(GrapeConfigParserWorkspace, self).__init__(
            workspaceDir=workspaceDir, configString=configString)
        grapeMenu.menu().setDefaultConfig(self)
        self.read(os.path.join(utility.workspaceDir(), self.GRAPE_CONFIG))
