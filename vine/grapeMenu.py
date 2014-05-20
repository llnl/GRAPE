import addSubproject
import bundle
import branches
import checkout
import clone
import commit
import config
import deleteBranch
import foreach
import grapeConfig
import grapeGit as git
import hooks
import merge
import mergeDevelop
import mergeRemote
import newFlowBranch
import newWorkingTree
import publish
import push
import quit
import resolveConflicts
import resumable
import review
import status
import test
import updateLocal
import updateView
import utility
import version
import walkthrough


#######################################################################
#The Menu class - encapsulates menu options and sections.
# Menu Options are the objects that perform git-related or stash-related tasks.
# sections are groupings of menu options that are displayed together.
######################################################################
__menuInstance = None


def menu():
    global __menuInstance
    if __menuInstance is None:
        __menuInstance = _Menu()
        grapeConfig.readDefaults()
        grapeConfig.read()
        __menuInstance.postInit()
    return __menuInstance


def _resetMenu():
    """
    Resets the Singleton Instance. Meant for testing purposes only.

    """
    global __menuInstance
    __menuInstance = None
    grapeConfig.resetGrapeConfig()


class _Menu(object):
    def __init__(self):
        self._options = {}
        #Add menu classes
        self._optionLookup = {}
        #Add/order your menu option here
        self._options = [addSubproject.AddSubproject(), bundle.Bundle(), bundle.Unbundle(), branches.Branches(),
                         status.Status(), checkout.Checkout(), push.Push(), commit.Commit(), publish.Publish(),
                         clone.Clone(), config.Config(), grapeConfig.WriteConfig(),
                         foreach.ForEach(), merge.Merge(), mergeDevelop.MergeDevelop(), mergeRemote.MergeRemote(),
                         deleteBranch.DeleteBranch(), newWorkingTree.NewWorkingTree(),
                         resolveConflicts.ResolveConflicts(),
                         review.Review(), test.Test(), updateLocal.UpdateLocal(),
                         hooks.InstallHooks(), hooks.RunHook(),
                         updateView.UpdateView(), version.Version(), walkthrough.Walkthrough(), quit.Quit()]

        #Add/order the menu sections here
        self._sections = ['Getting Started', 'Code Reviews', 'Workspace',
                          'Merge', 'Gitflow Tasks', 'Hooks', 'Patches', 'Project Management', 'Other']

    def postInit(self):
        # add dynamically generated (dependent on grapeConfig) options here
        self._options = self._options + newFlowBranch.NewBranchOptionFactory().createNewBranchOptions(grapeConfig.
                                                                                                      grapeConfig())
        for currOption in self._options:
            self._optionLookup[currOption.key] = currOption

    #######      MENU STUFF         #########################################################################
    def getOption(self, choice):
        try:
            return self._optionLookup[choice]
        except KeyError:
            print("Unknown option '%s'" % choice)
            return None

    def applyMenuChoice(self, choice, args=None, option_args=None):

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
            #print("applyMenuCHoice:",args)
            try:
                option_args = utility.parseArgs(chosen_option.__doc__, args[1:])
            except SystemExit as e:
                if len(args) > 1 and "--help" != args[1] and "-h" != args[1]:
                    print("GRAPE PARSING ERROR: could not parse %s\n" % (args[1:]))
                raise e
        try:
            if isinstance(chosen_option, resumable.Resumable):
                if option_args["--continue"]:
                    return chosen_option._resume(option_args)

            return chosen_option.execute(option_args)
        except git.GrapeGitError as e:
            print ("GRAPE GIT: Uncaught Error in grape-%s when executing '%s' in '%s'\n%s" %
                   (chosen_option._key,  e.gitCommand, e.cwd, e.gitOutput))
            exit(e.code)

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
                print("%s: %s" % (currOption.key.ljust(longest_key), currOption.description()))

    # configures a ConfigParser object with all default values and sections needed by our Option objects
    def setDefaultConfig(self, cfg):
        cfg.ensureSection("repo")
        cfg.set("repo", "name", "repo_name_not.yet.configured")
        cfg.set("repo", "url", "https://not.yet.configured/scm/project/unknown.git")
        cfg.set("repo", "httpsbase", "https://not.yet.configured")
        cfg.set("repo", "sshbase", "ssh://git@not.yet.configured")
        for currOption in self._options:
            currOption.setDefaultConfig(cfg)
