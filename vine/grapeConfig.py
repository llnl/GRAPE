import ConfigParser,os
import utility
import grapeMenu
import grapeGit as git
import option


__configInstance = None

def grapeConfig():
    global __configInstance
    if __configInstance == None:
        __configInstance = ConfigParser.ConfigParser()
    return __configInstance

def read(additionalFileNames = []):
    # initialize a ConfigParser with all defaults needed by the grapeMenu
    
    grapeMenu.menu().setDefaultConfig(grapeConfig())
    defaultFiles = []
    if os.name=="nt" :
      defaultFiles.append(os.path.join(os.environ["USERPROFILE"], ".grapeconfig"))
    else :
      defaultFiles.append(os.path.join(os.environ["HOME"], ".grapeconfig"))
    globalconfigfile = defaultFiles[0]
    try:
        defaultFiles.append(os.path.join(git.baseDir(),".grapeconfig"))
    except:
        pass
    try:
        defaultFiles.append(os.path.join(git.baseDir(),".grapeuserconfig"))
    except:
        pass
    files = defaultFiles + additionalFileNames
    readFiles = grapeConfig().read(files)
    if len(readFiles) == 0:
        utility.writeDefaultConfig(globalconfigfile)

class ConfigPairDict(dict):
    def __init__(self,pairDict): 
        self.data = pairDict

    def __getitem__(self,key): 
        try: 
            return self.data[key]
        except KeyError as e: 
            if '?' in self.data.keys():
                return self.data['?']
            else:
                print("GRAPE CONFIG ERROR: No value found for %s, no default '?':<value> in config.")
                raise e

def parseConfigPairList(string):
    pairs = string.split(' ')
    pairDict = None
    if pairs[0].strip().lower() != "none": 
        pairDict = {}
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

    def execute(self,args): 
        config = grapeConfig()
        with open(args["<file>"],'w') as f: 
            config.write(f)

    
