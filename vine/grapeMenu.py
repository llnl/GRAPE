import bundle, branches, clone, config, feature, gitflowHelp, grapeConfig
import hotfix, merge, mergeAbort, mergeDevelop, mergeRemote
import minorRelease, newFlowBranch, newWorkingTree, option, p4Import 
import p4Export, quit
import resolveConflicts, review, status, test
import updateLocal, updateView, utility, walkthrough
import deleteBranch, hooks
#######################################################################
#The Menu class - encapsulates menu options and sections.
# Menu Options are the objects that perform git-related or stash-related tasks.
# sections are groupings of menu options that are displayed together.
######################################################################
__menuInstance = None

def menu():
    global __menuInstance
    if __menuInstance == None:
        __menuInstance = _Menu()
        grapeConfig.read()
        __menuInstance.postInit()
    return __menuInstance

class _Menu(object):
    def __init__(self):
        self._options = {}
        #Add menu classes
        self._optionLookup = {}
        #Add/order your menu option here
        self._options = [bundle.Bundle(), bundle.Unbundle(), branches.Branches(), status.Status(),clone.Clone(), 
                          config.Config(), 
                          #feature.Feature(), 
                          #gitflowHelp.GitflowHelp(), hotfix.Hotfix(), 
                          merge.Merge(), mergeDevelop.MergeDevelop(), mergeRemote.MergeRemote(), 
                          #minorRelease.MinorRelease(),
                          deleteBranch.DeleteBranch(),newWorkingTree.NewWorkingTree(),
                          #p4Export.P4Export(), 
                          #p4Import.P4Import(),
                          resolveConflicts.ResolveConflicts(), 
                          review.Review(), test.Test(), updateLocal.UpdateLocal(), 
                          hooks.InstallHooks(),hooks.RunHook(), 
                          updateView.UpdateView(), walkthrough.Walkthrough(), quit.Quit()]



    #Add/order the menu sections here
        self._sections = ['Getting Started', 'Code Reviews', 'Miscellaneous', \
                        'Merge', 'Gitflow Tasks', 'Hooks','Patches', 'Other' ] #'Perforce Integration', 'Other']

    



    def postInit(self): 
         # add dynamically generated (dependent on grapeConfig) options here
        self._options = self._options + newFlowBranch.NewBranchOptionFactory().createNewBranchOptions(grapeConfig.grapeConfig()) 
        for currOption in self._options:
            self._optionLookup[currOption.key] = currOption

    #######      MENU STUFF         #########################################################################
    def getOption(self,choice):
        try:
            return self._optionLookup[choice]
        except:
            print("Unknown option '%s'" % choice)
            return None

    def applyMenuChoice(self,choice,args):
        chosenOption = self.getOption(choice)
        if chosenOption is None:
            return False
        # use optdoc to parse arguments to the chosenOption. 
        # utility.argParse also does the magic of filling in defaults from the config files as appropriate. 
        optionArgs = None
        if chosenOption.__doc__: 
            #print("applyMenuCHoice:",args)
            optionArgs = utility.parseArgs(chosenOption.__doc__,args[1:])
        return chosenOption.execute(optionArgs)

    # Present the main menu
    def presentTextMenu(self):
        width = 60
        print("GRAPE - Git Replacement for \"Awesome\" PARSEC Environment".center(width,'*'))

        longestKey = 0
        for currOption in self._options:
            if len(currOption.key) > longestKey:
                longestKey = len(currOption.key)

        for currSection in self._sections:
            loweredSection = currSection.strip().lower()
            print("\n" + (" %s " % currSection).center(width,'*'))
            for currOption in self._options:
                if currOption.section.strip().lower() != loweredSection:
                    continue
                print("%s: %s" % (currOption.key.ljust(longestKey), currOption.description()))

    # configures a ConfigParser object with all default values and sections needed by our Option objects
    def setDefaultConfig(self,config):
      config.add_section("repo")
      config.set("repo","name","repo_name_not.yet.configured")
      config.set("repo","url","https://not.yet.configured/scm/project/unknown.git")
      config.set("repo","httpsbase","https://not.yet.configured")
      config.set("repo","sshbase","ssh://git@not.yet.configured")
      for currOption in self._options:
         currOption.setDefaultConfig(config)
