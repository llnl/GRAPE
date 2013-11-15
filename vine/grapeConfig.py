import ConfigParser, os
import utility

__configInstance = None

def grapeConfig():
    global __configInstance
    if __configInstance == None:
        __configInstance = ConfigParser.ConfigParser()
    return __configInstance

def read(additionalFileNames = []):
    globalconfigfile = os.path.join(os.environ["HOME"],".grapeconfig")
    defaultFiles = [globalconfigfile,".grapeconfig",".grapeuserconfig"]
    files = defaultFiles + additionalFileNames
    readFiles = grapeConfig().read(files)
    if len(readFiles) == 0:
        utility.writeDefaultConfig(globalconfigfile)
