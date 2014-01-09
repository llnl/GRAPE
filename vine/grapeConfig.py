import ConfigParser, os
import utility
import grapeMenu

__configInstance = None

def grapeConfig():
    global __configInstance
    if __configInstance == None:
        __configInstance = ConfigParser.ConfigParser()
    return __configInstance

def read(additionalFileNames = []):
    # initialize a ConfigParser with all defaults needed by the grapeMenu
    grapeMenu.menu().setDefaultConfig(grapeConfig())
    globalconfigfile = os.path.join(os.environ["HOME"], ".grapeconfig")
    defaultFiles = [globalconfigfile, ".grapeconfig", ".grapeuserconfig"]
    files = defaultFiles + additionalFileNames
    readFiles = grapeConfig().read(files)
    if len(readFiles) == 0:
        utility.writeDefaultConfig(globalconfigfile)
