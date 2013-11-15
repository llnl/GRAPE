__configInstance = None

def Config():
    if __configInstance == None:
        __configInstance = ConfigParser.ConfigParser()
    return __configInstance

