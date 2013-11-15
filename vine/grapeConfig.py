__configInstance = None

def grapeConfig():
    if __configInstance == None:
        __configInstance = ConfigParser.ConfigParser()
    return __configInstance

