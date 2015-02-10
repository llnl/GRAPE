import ConfigParser
import os

import utility
import grapeMenu
import grapeGit as git
import option
import config as configOption


__configInstance = None

# returns the current configuration. This includes global configs, .grapeconfigs, and .grapeuserconfigs.
def grapeConfig():
    global __configInstance
    if __configInstance is None:
        __configInstance = GrapeConfigParser()
        readGlobal()
    return __configInstance


# returns a config object that only has the state associated with defaults and the current workspace's .grapeconfig,
# unaffected by .grapeuserconfig or $HOME/.grapeconfig
def workspaceConfig():
    wsConfig = GrapeConfigParser()
    readDefaults(wsConfig)
    wsConfig.readWorkspaceGrapeConfigFile()
    return wsConfig


# returns a config object that only has the state associated with the user's .grapeuserconfig
def grapeUserConfig():
    userConfig = GrapeConfigParser()
    userConfig.readWorkspaceUserConfigFile()
    return userConfig


# overwrite the global config with the given repo's .grapeconfig
def grapeRepoConfig(repoPath): 
    repoConfig = grapeConfig()
    repoConfig.read(os.path.join(repoPath,".grapeconfig"))
    return repoConfig

def resetGrapeConfig(newInstance=None):
    """
    Resets the singleton instance.
    """
    global __configInstance
    __configInstance = newInstance


def readDefaults(config=None):
    if config is None:
        config = grapeConfig()
    grapeMenu.menu().setDefaultConfig(config)


def readGlobal():
    globalconfigfile = os.path.join(utility.getHomeDirectory(), ".grapeconfig")
    grapeConfig().read([globalconfigfile])


def read(additionalFileNames=None):
    # initialize a ConfigParser with all defaults needed by the grapeMenu
    if additionalFileNames is None:
        additionalFileNames = []
    defaultFiles = []
    if os.name == "nt":
        defaultFiles.append(os.path.join(os.environ["USERPROFILE"], ".grapeconfig"))
    else:
        defaultFiles.append(os.path.join(os.environ["HOME"], ".grapeconfig"))
    globalconfigfile = defaultFiles[0]
    try:
        defaultFiles.append(os.path.join(utility.workspaceDir(warnIfNotFound=False), ".grapeconfig"))
    except:
        pass
    try:
        defaultFiles.append(os.path.join(utility.workspaceDir(warnIfNotFound=False), ".git", ".grapeuserconfig"))
    except:
        pass

    files = defaultFiles + additionalFileNames
    readFiles = grapeConfig().read(files)
    if len(readFiles) == 0:
        utility.writeDefaultConfig(globalconfigfile)


class ConfigPairDict(dict):

    def __getitem__(self, key):
        try:
            return super(ConfigPairDict, self).__getitem__(key)
        except KeyError as e: 
            if '?' in self.keys():
                return self['?']
            else:
                e.message = "GRAPE CONFIG ERROR: No value found for %s, no default '?':<value> in config." % key
                raise e


class GrapeConfigParser(ConfigParser.ConfigParser):
    def __init__(self, workspaceDir=None):
        ConfigParser.ConfigParser.__init__(self)
        if workspaceDir:
            self.read(os.path.join(workspaceDir,".grapeconfig"))

    def readWorkspaceGrapeConfigFile(self):
        self.read(os.path.join(utility.workspaceDir(), ".grapeconfig"))

    def readWorkspaceUserConfigFile(self):
        try:
            self.read(os.path.join(utility.workspaceDir(), ".git", ".grapeuserconfig"))
        except IOError:
            pass

    def readGlobalGrapeConfigFile(self):
        if os.name == "nt":
            fname = os.path.join(os.environ["USERPROFILE"], ".grapeconfig")
        else:
            fname = os.path.join(os.environ["HOME"], ".grapeconfig")
        self.read(fname)

    def getMapping(self, section, cfgOption, raw=False, cfgVars=None):
        return self.parseConfigPairList(self.get(section, cfgOption, raw=raw, vars=cfgVars))

    def getList(self, section, cfgOption, raw=False, cfgVars=None):
        return self.get(section, cfgOption, raw=raw, vars=cfgVars).split()

    def getPublicBranchFor(self, branch, getDestinationBranch=True):
        if getDestinationBranch:
            destinationBranches = self.getMapping("flow", "topicDestinationMappings")
            try:
                destinationBranch = destinationBranches[git.branchPrefix(branch)]
                return destinationBranch
            except KeyError:
                pass

        publicBranches = self.get("flow", "publicbranches").split()
        if branch in publicBranches:
            return branch
        publicMapping = self.getMapping("flow", "topicPrefixMappings")
        return publicMapping[git.branchPrefix(branch)]

    def ensureSection(self, section):
        try:
            self.add_section(section)
            if "nested-" in section: 
                self.set(section,"active","False")
        except ConfigParser.DuplicateSectionError:
            pass
 

    def getAllNestedSubprojects(self):
        list = []
        try:
           list = self.getList("nestedProjects", "names")
        except: 
            pass
        finally:
            return list
        
    @staticmethod
    def getAllActiveNestedSubprojects(workspaceDir=None):
        config = grapeConfig() if workspaceDir is None else GrapeConfigParser(workspaceDir) 
        allNested = config.getAllNestedSubprojects()
        userConfig = grapeUserConfig()
        active = []
        for sub in allNested:
            try:
                if userConfig.getboolean("nested-%s" % sub, "active"):
                    active.append(sub)
            except ConfigParser.Error:
                userConfig.ensureSection("nested-%s" % sub)
                userConfig.set("nested-%s" % sub, "active", "False")
        return active

    @staticmethod
    def getAllActiveNestedSubprojectPrefixes(workspaceDir = None): 
        config = grapeConfig() if (workspaceDir is None or workspaceDir is utility.workspaceDir()) else GrapeConfigParser(workspaceDir) 
        return [config.get("nested-%s" % name, "prefix") for name in GrapeConfigParser.getAllActiveNestedSubprojects(workspaceDir)]

    @staticmethod
    def getAllModifiedNestedSubprojects(since, now="HEAD", workspaceDir=None): 
        config = grapeConfig() if workspaceDir is None else GrapeConfigParser(workspaceDir) 
        publicBranches = config.getList("flow","publicbranches")
        if workspaceDir is None:
            workspaceDir = utility.workspaceDir()
        active = GrapeConfigParser.getAllActiveNestedSubprojects(workspaceDir)
        modified = []
        cwd = os.getcwd()
        for repo in active:
            prefix = config.get("nested-%s" % repo, "prefix")
            os.chdir(os.path.join(workspaceDir,prefix))
            configOption.Config.ensurePublicBranchesExist(config,os.path.join(workspaceDir,prefix), publicBranches)

            if git.diff("--name-only %s %s" % (since, now), quiet=True): 
                modified.append(repo)

        os.chdir(cwd)
        return modified
    
    @staticmethod
    def getAllModifiedNestedSubprojectPrefixes(since, now="HEAD", workspaceDir=None): 
        config = grapeConfig() if workspaceDir is None else GrapeConfigParser(workspaceDir) 
        return [config.get("nested-%s" % name, "prefix") for name in GrapeConfigParser.getAllModifiedNestedSubprojects(since,workspaceDir=workspaceDir)]
        
    def setActiveNestedSubprojects(self, listOfActiveSubprojects) :
        allNested = grapeConfig().getAllNestedSubprojects()
        active = {}
        for proj in allNested:
            active[proj] = False
        for proj in listOfActiveSubprojects:
            active[proj] = True
        for proj in active:
            section = "nested-%s" % proj
            self.ensureSection(section)
            self.set(section, "active", "True" if active[proj] is True else "False")

    @staticmethod
    def parseConfigPairList(toParse):

        pairs = toParse.split() if toParse else ["none"]
        pairDict = ConfigPairDict()
        if pairs[0].strip().lower() != "none":
            for pair in pairs:
                plist = pair.split(':')
                pairDict[plist[0]] = plist[1]
        return ConfigPairDict(pairDict)


class WriteConfig(option.Option):
    """
        grape writeConfig: Writes the current configuration to a file, using any configuration set
        by ~/.grapeconfig or your <REPO_BASE>/.grapeconfig. 

        Usage: 
        grape-writeConfig <file> [--gitflow]

    """
    def __init__(self): 
        self._section = "Getting Started"
        self._key = "writeConfig"
        self._config = None
    def description(self):
        return "write a .grapeconfig file based on your current environment"

    def execute(self, args):
        config = grapeConfig()

        self.setFlowModelConfig(config, args)
        writeConfig(config, args["<file>"])

    @staticmethod
    def setFlowModelConfig(config, args):
        config.ensureSection("flow")
        config.ensureSection("versioning")
        config.ensureSection("patch")
        if args["--gitflow"]:
            # [flow]
            config.set("flow", "publicBranches", "master develop")
            config.set("flow", "topicPrefixMappings",
                       "hotfix:master bugfix:develop feature:develop ?:develop release:develop")
            config.set("flow", "topicDestinationMappings", "release:master")
            config.set("flow", "publishpolicy", "?:merge master:cascade->develop")
            # [versioning]
            config.set("versioning", "updateTag", "True")
            config.set("versioning", "branchslotmappings", "?:3 master:2")
            # [patch]
            config.set("patch", "branches", "develop master")

    def setDefaultConfig(self, config):
        pass


def writeConfig(config, fname):
    with open(fname, 'w') as f:
        config.write(f)


