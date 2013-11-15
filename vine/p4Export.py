import option

# prepares all changes since the last p4 commit viewable from HEAD in your P4CLIENT (typically maindev)
class P4Export(option.Option):
    key = "p4export"
    section = "Perforce Integration"

    def Description(self):
        return "Prepare changes in current branch in your perforce maindev client"

    def Execute(self):
        #First, create a new branch and prepare it with a squashed version of your current branch.
        print("Preparing temporary branch to hold squashed version of current branch.")
        originalBranch = utility.GetCurrentBranch()
        options['dev'].Execute()
        tmpBranch = utility.GetCurrentBranch()
        git.merge("--squash",originalBranch)
        git.commit("-m","\"Squashed Merge from %s in preparation for p4 submit.\"" % originalBranch)
        print("Ready to perform git.p4 submit")
        #git.p4("submit","-M","--prepare-p4-only")
        print("P4 client prepared, no submit has occurred yet. Use precommit maindev to submit.")
        return True
