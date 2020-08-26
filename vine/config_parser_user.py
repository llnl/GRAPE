import configparser
import os
from vine import config_parser_base
from vine import config_parser_global


class GrapeConfigParserUser(config_parser_base.GrapeConfigParserBase):

    def __init__(self, configString=None, read_global=True, *, workspace_dir):
        super(GrapeConfigParserUser, self).__init__(
            workspaceDir=workspace_dir if read_global else None, configString=configString)
        self.workspace_dir = workspace_dir
        self.readWorkspaceUserConfigFile()
        # strip out everything except the relevant user configs
        old_sections = self.sections()
        for section in old_sections:
           if section.startswith("nested-"):
               for option in self.options(section):
                  if option != "active":
                     self.remove_option(section, option)
           else:
               self.remove_section(section)

    def readWorkspaceUserConfigFile(self):
        grape_user_config = os.path.join(self.workspace_dir, self.GIT_DIR,
                                         '.grapeuserconfig')
        self.read(grape_user_config)

    def setActiveNestedSubprojects(self, listOfActiveSubprojects):
        # clear out any old nested subproject sections
        old_sections = self.sections()
        for section in old_sections:
           if section.startswith("nested-"):
              self.remove_section(section)

        allNested = config_parser_global.grapeConfig().getAllNestedSubprojects()
        active = {}
        for proj in allNested:
            active[proj] = False
        for proj in listOfActiveSubprojects:
            active[proj] = True
        for proj in active:
            section = f"nested-{proj}"
            self.ensureSection(section)
            self.set(section, "active", "True" if active[proj] is True else "False")


def getAllActiveNestedSubprojects(*, workspaceDir):
    config = __get_global_grape_config(workspaceDir)
    allNested = config.getAllNestedSubprojects()
    userConfig = GrapeConfigParserUser(workspace_dir=workspaceDir)
    active = []
    for sub in allNested:
        try:
            if userConfig.getboolean(f"nested-{sub}", "active"):
                active.append(sub)
        except configparser.Error:
            userConfig.ensureSection(f"nested-{sub}")
            userConfig.set(f"nested-{sub}", "active", "False")
    return active


def getAllActiveNestedSubprojectPrefixes(*, workspaceDir):
    if workspaceDir is None:
        config = config_parser_global.grapeConfig()
    else:
        config = __get_global_grape_config(workspaceDir)
    return [config.get(f"nested-{name}", "prefix") for name in getAllActiveNestedSubprojects(workspaceDir=workspaceDir)]


def getAllModifiedNestedSubprojects(since, now="HEAD", *, workspaceDir):
    # Imported here to avoid circular dependencies
    from vine import config as configOption
    from vine import grapeGit as git

    config = __get_global_grape_config()
    publicBranches = config.getPublicBranchList()
    if workspaceDir is None:
        workspaceDir = self.workspace_dir
    active = getAllActiveNestedSubprojects(workspaceDir=workspaceDir)
    modified = []
    for repo in active:
        prefix = config.get(f"nested-{repo}", "prefix")
        repo_path = os.path.join(workspaceDir,prefix)
        configOption.Config.ensurePublicBranchesExist(repo_path, publicBranches)

        if git.log(f"--oneline {since}..{now}", execution_path=repo_path):
            modified.append(repo)

    return modified


def getAllModifiedNestedSubprojectPrefixes(since, *, workspaceDir):
    config = __get_global_grape_config()
    return [config.get(f"nested-{name}", "prefix") for name in getAllModifiedNestedSubprojects(since, workspaceDir=workspaceDir)]


def __get_global_grape_config(workspaceDir=None):
    """
    Intentionally returns GrapeConfigParserBase if no workspace dir given.
    """
    if not workspaceDir:
        return config_parser_global.grapeConfig()
    return config_parser_base.GrapeConfigParserBase(workspaceDir=workspaceDir)
