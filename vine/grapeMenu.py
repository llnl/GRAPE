import branches, clone, config, feature, gitflowHelp
import hotfix, merge, mergeAbort, mergeDevelop, mergeRemote
import minorRelease, newWorkingTree, option, p4Import, p4Export, quit
import resolveConflicts, review, test
import updateLocal, updateView, utility, walkthrough

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
    return __menuInstance

class _Menu(object):
    def __init__(self):
        self._options = {}
        #Add menu classes
        self._optionLookup = {}
        #Add/order your menu option here
        self._options = [branches.Branches(), clone.Clone(), config.Config(), feature.Feature(), \
                          gitflowHelp.GitflowHelp(), hotfix.Hotfix(), \
                          merge.Merge(), mergeDevelop.MergeDevelop(), mergeRemote.MergeRemote(), \
                          minorRelease.MinorRelease(), newWorkingTree.NewWorkingTree(), p4Export.P4Export(), \
                          p4Import.P4Import(), resolveConflicts.ResolveConflicts(), \
                          review.Review(), test.Test(), updateLocal.UpdateLocal(), \
                          updateView.UpdateView(), walkthrough.Walkthrough(), quit.Quit()]

    #Add/order the menu sections here
        self._sections = ['Getting Started', 'Code Reviews', 'Miscellaneous', \
                        'Merge', 'Gitflow Tasks', 'Perforce Integration', 'Other']

        for currOption in self._options:
            self._optionLookup[currOption.key] = currOption

    #######      MENU STUFF         #########################################################################
    def getOption(self,choice):
        try:
            return self._optionLookup[choice]
        except:
            print("Unknown option '%s'" % choice)
            return None

    def applyMenuChoice(self,choice):
        chosenOption = self.getOption(choice)
        if chosenOption is None:
            return False
        return chosenOption.execute()

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
