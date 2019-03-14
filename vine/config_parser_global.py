import os
import config_parser_base
import grapeMenu
import utility


__GLOBAL_CONFIG = None


def grapeConfig():
    """
    Returns the current configuration. This includes global configs,
    .grapeconfigs, and .grapeuserconfigs.
    """
    global __GLOBAL_CONFIG
    if __GLOBAL_CONFIG is None:
        __GLOBAL_CONFIG = config_parser_base.GrapeConfigParserBase()
        globalconfigfile = os.path.join(utility.getHomeDirectory(),
                                        __GLOBAL_CONFIG.GRAPE_CONFIG)
        __GLOBAL_CONFIG.read([globalconfigfile])
    return __GLOBAL_CONFIG


def resetGrapeConfig(newInstance=None):
    """
    Resets the singleton instance.
    """
    global __GLOBAL_CONFIG
    __GLOBAL_CONFIG = newInstance


def read(additionalFileNames=None):
    # initialize a ConfigParser with all defaults needed by the grapeMenu
    if additionalFileNames is None:
        additionalFileNames = []
    defaultFiles = []
    config_file_name = config_parser_base.GrapeConfigParserBase.GRAPE_CONFIG
    if os.name == "nt":
        config_path = os.environ["USERPROFILE"]
    else:
        config_path = os.environ["HOME"]
    defaultFiles.append(os.path.join(config_path, config_file_name))
    globalconfigfile = defaultFiles[0]
    try:
        defaultFiles.append(os.path.join(
            utility.workspaceDir(warn_if_not_found=False,
                                 throw_if_not_found=False),
            config_file_name))
    except:
        pass
    try:
        defaultFiles.append(os.path.join(
            utility.workspaceDir(warn_if_not_found=False,
                                 throw_if_not_found=False),
            ".git", ".grapeuserconfig"))
    except:
        pass

    files = defaultFiles + additionalFileNames
    readFiles = grapeConfig().read(files)
    if not readFiles:
        writeDefaultConfig(globalconfigfile)


# writes a config file with default options
def writeDefaultConfig(filename):
    config = config_parser_base.GrapeConfigParserBase()
    grapeMenu.menu().setDefaultConfig(config)
    with open(filename, 'w') as f:
        config.write(f)


def writeConfig(config, fname):
    with open(fname, 'w') as f:
        config.write(f)
