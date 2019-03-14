import ConfigParser
import os
import config_parser_base
import config_parser_global
import config as configOption
import grapeGit as git
import utility


class GrapeConfigParserUser(config_parser_base.GrapeConfigParserBase):

    def __init__(self, workspaceDir=None, configString=None):
        super(GrapeConfigParserUser, self).__init__(
            workspaceDir=workspaceDir, configString=configString)
        self.readWorkspaceUserConfigFile()

    def readWorkspaceUserConfigFile(self):
        try:
            self.read(os.path.join(utility.workspaceDir(),
                                   self.GIT_DIR, '.grapeuserconfig'))
        except IOError:
            pass

    def setActiveNestedSubprojects(self, listOfActiveSubprojects):
        allNested = config_parser_global.grapeConfig().getAllNestedSubprojects()
        active = {}
        for proj in allNested:
            active[proj] = False
        for proj in listOfActiveSubprojects:
            active[proj] = True
        for proj in active:
            section = "nested-%s" % proj
            self.ensureSection(section)
            self.set(section, "active", "True" if active[proj] is True else "False")


def getAllActiveNestedSubprojects(workspaceDir=None):
    config = __get_global_grape_config(workspaceDir)
    allNested = config.getAllNestedSubprojects()
    userConfig = GrapeConfigParserUser()
    active = []
    for sub in allNested:
        try:
            if userConfig.getboolean("nested-%s" % sub, "active"):
                active.append(sub)
        except ConfigParser.Error:
            userConfig.ensureSection("nested-%s" % sub)
            userConfig.set("nested-%s" % sub, "active", "False")
    return active


def getAllActiveNestedSubprojectPrefixes(workspaceDir=None):
    if workspaceDir is utility.workspaceDir():
        config = config_parser_global.grapeConfig()
    else:
        config = __get_global_grape_config(workspaceDir)
    return [config.get("nested-%s" % name, "prefix") for name in getAllActiveNestedSubprojects(workspaceDir)]


def getAllModifiedNestedSubprojects(since, now="HEAD", workspaceDir=None):
    config = __get_global_grape_config(workspaceDir)
    publicBranches = config.getPublicBranchList()
    if workspaceDir is None:
        workspaceDir = utility.workspaceDir()
    active = getAllActiveNestedSubprojects(workspaceDir)
    modified = []
    cwd = os.getcwd()
    for repo in active:
        prefix = config.get("nested-%s" % repo, "prefix")
        os.chdir(os.path.join(workspaceDir,prefix))
        configOption.Config.ensurePublicBranchesExist(os.path.join(workspaceDir, prefix), publicBranches)

        if git.log("--oneline %s..%s" % (since, now)):
            modified.append(repo)

    os.chdir(cwd)
    return modified


def getAllModifiedNestedSubprojectPrefixes(since, now="HEAD", workspaceDir=None):
    config = __get_global_grape_config(workspaceDir)
    return [config.get("nested-%s" % name, "prefix") for name in getAllModifiedNestedSubprojects(since, workspaceDir=workspaceDir)]


def __get_global_grape_config(workspaceDir=None):
    """
    Intentionally returns GrapeConfigParserBase if no workspace dir given.
    """
    if not workspaceDir:
        return config_parser_global.grapeConfig()
    return config_parser_base.GrapeConfigParserBase(workspaceDir=workspaceDir)
