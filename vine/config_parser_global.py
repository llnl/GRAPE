import io
import os
from grape.vine import config_parser_base
from grape.vine import utility


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

    workspace_dir = utility.workspaceDir()
    if not workspace_dir:
        print("GRAPE Warning: expected to be in your workspace, " +
              "no .git directory found")
    else:
        config_file_path = os.path.join(workspace_dir, config_file_name)
        defaultFiles.append(config_file_path)
        grape_user_config_path = os.path.join(workspace_dir, '.git',
                                              '.grapeuserconfig')
        defaultFiles.append(grape_user_config_path)

    files = defaultFiles + additionalFileNames
    readFiles = grapeConfig().read(files)
    if not readFiles:
        writeDefaultConfig(globalconfigfile)


# writes a config file with default options
def writeDefaultConfig(filename):
    from grape.vine import grapeMenu

    config = config_parser_base.GrapeConfigParserBase()
    grapeMenu.menu().setDefaultConfig(config)
    with io.open(filename, 'w') as f:
        config.write(f)


def writeConfig(config, fname):
    with io.open(fname, 'w') as f:
        config.write(f)
