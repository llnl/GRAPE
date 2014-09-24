import ConfigParser
import os

import utility
import grapeMenu
import grapeGit as git
import option


__configInstance = None


def grapeConfig():
    global __configInstance
    if __configInstance is None:
        __configInstance = GrapeConfigParser()
        readGlobal()
    return __configInstance

def resetGrapeConfig(newInstance=None):
    """
    Resets the singleton instance.
    """
    global __configInstance
    __configInstance = newInstance

def readDefaults():
    grapeMenu.menu().setDefaultConfig(grapeConfig())

def readGlobal():
    if os.name == "nt":
        globalconfigfile = os.path.join(os.environ["USERPROFILE"], ".grapeconfig")
    else:
        globalconfigfile = os.path.join(os.environ["HOME"], ".grapeconfig")
    grapeConfig().read([globalconfigfile])


def read(additionalFileNames=[]):
    # initialize a ConfigParser with all defaults needed by the grapeMenu

    defaultFiles = []
    if os.name == "nt":
        defaultFiles.append(os.path.join(os.environ["USERPROFILE"], ".grapeconfig"))
    else:
        defaultFiles.append(os.path.join(os.environ["HOME"], ".grapeconfig"))
    globalconfigfile = defaultFiles[0]
    try:
        defaultFiles.append(os.path.join(git.baseDir(), ".grapeconfig"))
    except:
        pass
    try:
        defaultFiles.append(os.path.join(git.baseDir(), ".grapeuserconfig"))
    except:
        pass
    files = defaultFiles + additionalFileNames
    readFiles = grapeConfig().read(files)
    if len(readFiles) == 0:
        utility.writeDefaultConfig(globalconfigfile)


class ConfigPairDict(dict):

    def __getitem__(self,key): 
        try:
            return super(ConfigPairDict,self).__getitem__(key)
        except KeyError as e: 
            if '?' in self.keys():
                return self['?']
            else:
                e.message = "GRAPE CONFIG ERROR: No value found for %s, no default '?':<value> in config." % key
                raise e


class GrapeConfigParser(ConfigParser.ConfigParser):
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
        except ConfigParser.DuplicateSectionError:
            pass

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
            config.set("flow", "topicPrefixMappings", "hotfix:master bugfix:develop feature:develop ?:develop release:develop")
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


