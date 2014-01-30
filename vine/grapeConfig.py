import ConfigParser, os
import utility
import grapeMenu
import grapeGit as git

__configInstance = None

def grapeConfig():
    global __configInstance
    if __configInstance == None:
        __configInstance = ConfigParser.ConfigParser()
    return __configInstance

def read(additionalFileNames = []):
    # initialize a ConfigParser with all defaults needed by the grapeMenu
    grapeMenu.menu().setDefaultConfig(grapeConfig())
    if os.name=="nt" :
      globalconfigfile = os.path.join(os.environ["USERPROFILE"], ".grapeconfig")
    else :
      globalconfigfile = os.path.join(os.environ["HOME"], ".grapeconfig")

    grapeConfigFile = os.path.join(git.baseDir(),".grapeconfig")
    grapeUserConfigFile = os.path.join(git.baseDir(),".grapeuserconfig")
    defaultFiles = [globalconfigfile, grapeConfigFile, grapeUserConfigFile]
    files = defaultFiles + additionalFileNames
    readFiles = grapeConfig().read(files)
    if len(readFiles) == 0:
        utility.writeDefaultConfig(globalconfigfile)


