import ConfigParser,os
import utility
import grapeMenu
import grapeGit as git
import option


__configInstance = None


def grapeConfig():
    global __configInstance
    if __configInstance is None:
        __configInstance = ConfigParser.ConfigParser()
    return __configInstance

def resetGrapeConfig(newInstance=None):
    """
    Resets the singleton instance.
    """
    global __configInstance
    __configInstance = newInstance


def read(additionalFileNames=[]):
    # initialize a ConfigParser with all defaults needed by the grapeMenu

    grapeMenu.menu().setDefaultConfig(grapeConfig())
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
                print("GRAPE CONFIG ERROR: No value found for %s, no default '?':<value> in config.")
                raise e


def parseConfigPairList(string):
    pairs = string.split(' ')
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
        grape-writeConfig <file>

    """
    def __init__(self): 
        self._section = "Getting Started"
        self._key = "writeConfig"

    def description(self):
        return "write a .grapeconfig file based on your current environment"

    def execute(self, args):
        config = grapeConfig()
        writeConfig(config, args["<file>"])

    def setDefaultConfig(self, config):
        pass


def writeConfig(config, fname):
    with open(fname, 'w') as f:
        config.write(f)


def ensureSection(config, section):
    try:
        config.add_section(section)
    except ConfigParser.DuplicateSectionError:
        pass
