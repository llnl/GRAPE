import io
import os
from vine import config_parser_base


__GLOBAL_CONFIG = None


def grapeConfig():
    """
    Returns the current configuration. This includes global configs,
    .grapeconfig, and .grapeuserconfig.
    """
    global __GLOBAL_CONFIG
    if __GLOBAL_CONFIG is None:
        home = get_env_config_path()
        __GLOBAL_CONFIG = config_parser_base.GrapeConfigParserBase(home)
    return __GLOBAL_CONFIG


def resetGrapeConfig(newInstance=None):
    """
    Resets the singleton instance.
    """
    global __GLOBAL_CONFIG
    __GLOBAL_CONFIG = newInstance


def get_env_config_path():
    if os.name == "nt":
        return os.environ["USERPROFILE"]
    return os.environ["HOME"]


def read(additionalFileNames=None, *, workspace_dir):
    # initialize a ConfigParser with all defaults needed by the grapeMenu
    if additionalFileNames is None:
        additionalFileNames = []
    defaultFiles = []
    config_file_name = config_parser_base.GrapeConfigParserBase.GRAPE_CONFIG
    config_path = get_env_config_path()
    defaultFiles.append(os.path.join(config_path, config_file_name))
    globalconfigfile = defaultFiles[0]

    config_file_path = os.path.join(workspace_dir, config_file_name)
    defaultFiles.append(config_file_path)
    grape_user_config_path = os.path.join(workspace_dir, '.git',
                                          '.grapeuserconfig')
    if os.path.exists(grape_user_config_path):
        defaultFiles.append(grape_user_config_path)

    files = defaultFiles + additionalFileNames
    readFiles = grapeConfig().read(files)
    if not readFiles:
        writeDefaultConfig(globalconfigfile)


# writes a config file with default options
def writeDefaultConfig(filename):
    from vine import grapeMenu

    config = config_parser_base.GrapeConfigParserBase()
    grapeMenu.menu().setDefaultConfig(config)
    with io.open(filename, 'w') as f:
        config.write(f)


def writeConfig(config, fname):
    with io.open(fname, 'w') as f:
        config.write(f)
