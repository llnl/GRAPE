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


