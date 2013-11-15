import ConfigParser, os

__configInstance = None

def grapeConfig():
    global __configInstance
    if __configInstance == None:
        __configInstance = ConfigParser.ConfigParser()
    return __configInstance

def read():
    globalconfigfile = os.path.join(os.environ["HOME"],".grapeconfig")
    readFiles = grapeConfig().read([globalconfigfile,".grapeconfig",".grapeuserconfig"])
    if len(readFiles) == 0:
        utility.writeDefaultConfig(globalconfigfile)
