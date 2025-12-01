import logging
import os
import traceback

from vine import addSubproject
from vine import approve
from vine import bundle
from vine import branches
from vine import checkout
from vine import clone
from vine import commit
from vine import config
from vine import config_parser_global
from vine import deleteBranch
from vine import foreach
from vine import gitlabAdmin
from vine import grape_errors
from vine import writeConfig
from vine import hooks
from vine import merge
from vine import mergeDown
from vine import mergeRemote
from vine import multi_repo_cmd_launcher
from vine import newFlowBranch
from vine import pull
from vine import push
from vine import quit
from vine import resolveConflicts
from vine import resumable
from vine import review
from vine import stash
from vine import status
from vine import grapeTest as test
from vine import updateLocal
from vine import updateView
from vine import utility
from vine import version
from vine import vine_logging
from vine import walkthrough
from vine.workspace_dir_handler import WorkspaceDirHandler


#######################################################################
#The Menu class - encapsulates menu options and sections.
# Menu Options are the objects that perform git-related or bitbucket-related tasks.
# sections are groupings of menu options that are displayed together.
######################################################################
__menuInstance = None


def menu(workspace_dir=None):
    global __menuInstance
    if __menuInstance is None:
        __menuInstance = _Menu()

        # __menuInstance process workspace_dir via @workspace_dir.setter in WorkspaceDirHandler
        # After processing, __menuInstance.workspace_dir may be a parent dir or workspace_dir
        __menuInstance.set_workspace_dir(workspace_dir)
        menu_workspace_dir = __menuInstance.workspace_dir

        config = config_parser_global.grapeConfig()
        menu().setDefaultConfig(config)
        config_parser_global.read(workspace_dir=menu_workspace_dir)
        __menuInstance.postInit()
    elif workspace_dir:
        __menuInstance.set_workspace_dir(workspace_dir)
    return __menuInstance


def _resetMenu():
    """
    Resets the Singleton Instance. Meant for testing purposes only.

    """
    global __menuInstance
    __menuInstance = None
    config_parser_global.resetGrapeConfig()


class _Menu(WorkspaceDirHandler):

    def __init__(self):
        super(_Menu, self).__init__()
        # Imported here to avoid circular dependencies
        from vine import publish

        #Add menu classes
        self._optionLookup = {}
        #Add/order your menu option here
        self._options = [
            addSubproject.AddSubproject(), approve.Approve(), bundle.Bundle(),
            bundle.Unbundle(), branches.Branches(), status.Status(), stash.Stash(),
            checkout.Checkout(), push.Push(), pull.Pull(), commit.Commit(),
            publish.Publish(), clone.Clone(), config.Config(),
            writeConfig.WriteConfig(), foreach.ForEach(), merge.Merge(),
            mergeDown.MergeDown(), mergeRemote.MergeRemote(),
            deleteBranch.DeleteBranch(), resolveConflicts.ResolveConflicts(),
            review.Review(), test.Test(), updateLocal.UpdateLocal(),
            hooks.InstallHooks(), hooks.RunHook(), updateView.UpdateView(),
            version.Version(), walkthrough.Walkthrough(),
            gitlabAdmin.GitlabAdmin(), quit.Quit()
            ]

        self.set_workspace_dir(os.getcwd())

        #Add/order the menu sections here
        self._sections = [
            'Getting Started', 'Code Reviews', 'Workspace', 'Merge',
            'Gitflow Tasks', 'Hooks', 'Patches', 'Project Management', 'Other'
            ]

    def set_workspace_dir(self, workspace_dir):
        self.workspace_dir = workspace_dir
        for menu_option in self._options:
            if isinstance(menu_option, WorkspaceDirHandler):
                menu_option.workspace_dir = workspace_dir

    def postInit(self):
        # add dynamically generated (dependent on grapeConfig) options here
        branch_option_factory = newFlowBranch.NewBranchOptionFactory()
        new_option_list = branch_option_factory.createNewBranchOptions(
            config_parser_global.grapeConfig(),
            execution_path=self.workspace_dir)
        self._options.extend(new_option_list)

        for currOption in self._options:
            self._optionLookup[currOption.key] = currOption

    #######      MENU STUFF         #########################################################################
    def hasOption(self, choice):
        return choice in self._optionLookup.keys()

    def getOption(self, choice):
        try:
            return self._optionLookup[choice]
        except KeyError:
            logging.info(f"Unknown option '{choice}'\n {self._optionLookup}")
            raise Exception
            return None

    def applyMenuChoice(self, choice, args=None, option_args=None):
        logging.debug(f"Executing applyMenuChoice {choice} with args: {args} and option_args: {option_args}")
        chosen_option = self.getOption(choice)
        if chosen_option is None:
            return False
        if args is None or len(args) == 0:
            args = [chosen_option._key]
        #first argument better be the key
        if args[0] != chosen_option._key:
            args = [chosen_option._key]+args

        # use optdoc to parse arguments to the chosen_option.
        # utility.argParse also does the magic of filling in defaults from the config files as appropriate.
        if option_args is None and chosen_option.__doc__:
            try:
                config = config_parser_global.grapeConfig()
                option_args = utility.parseArgs(chosen_option.__doc__, args[1:], config)
            except SystemExit as e:
                # 'docopt' prints help doc then exists with SystemExit.
                if len(args) > 1 and "--help" != args[1] and "-h" != args[1]:
                    print(f"GRAPE PARSING ERROR: could not parse {args[1:]}\n")
                raise e
        try:
            if isinstance(chosen_option, resumable.Resumable):
                if option_args["--continue"]:
                    return chosen_option._resume(
                        option_args, workspace_dir=chosen_option.workspace_dir)
            return chosen_option.execute(option_args)

        except grape_errors.GrapeGitError as e:
            logging.error(traceback.print_exc())
            if e.authError:
                logging.error(f"\n\n************************** AUTHENTICATION ERROR ********************************\n" +
                              "You may need to reset your git credential cache or issue a simple git\n" +
                              "command to cache your credentials.\n"+
                              "********************************************************************************")
            else:
                logging.error(f"GRAPE: Uncaught Error {e.code} in " +
                      f"grape-{chosen_option._key} when executing " +
                      f"'{e.gitCommand}' in '{e.cwd}'\n{e.gitOutput}")
            exit(e.code)

        except grape_errors.NoWorkspaceDirException as e:
            logging.error(f"GRAPE: grape {chosen_option.key} must be run" +
                          " from a grape workspace.")
            logging.error(f"GRAPE: {e.message}")
            exit(1)

    # Present the main menu
    def presentTextMenu(self):
        width = 60
        print("GRAPE - Git Replacement for \"Awesome\" PARSEC Environment".center(width, '*'))

        longest_key = 0
        for currOption in self._options:
            if len(currOption.key) > longest_key:
                longest_key = len(currOption.key)

        for currSection in self._sections:
            lowered_section = currSection.strip().lower()
            print("\n" + (" %s " % currSection).center(width, '*'))
            for currOption in self._options:
                if currOption.section.strip().lower() != lowered_section:
                    continue
                print(f"{currOption.key.ljust(longest_key)}: {currOption.description()}")

    # configures a ConfigParser object with all default values and sections needed by our Option objects
    def setDefaultConfig(self, cfg):
        cfg.ensureSection("repo")
        cfg.set("repo", "name", "repo_name_not.yet.configured")
        cfg.set("repo", "url", "https://not.yet.configured/scm/project/unknown.git")
        cfg.set("repo", "httpsbase", "https://not.yet.configured")
        cfg.set("repo", "sshbase", "ssh://git@not.yet.configured")
        for currOption in self._options:
            currOption.setDefaultConfig(cfg)
        multi_repo_cmd_launcher.setDefaultConfig(cfg)
