import option

#imports recent changes in perforce into a hotfix branch ready for tagging and merging to master
class P4Import(option.Option):
    key = "p4import"
    section = "Perforce Integration"

    def Description(self):
        return "Import recent p4 changes into a hotfix branch"

    def Execute(self):
        print("calling Grape hot")
        proceed = options['hot'].Execute()
        assert proceed == True
        print("importing recent p4 changes into p4 master...")
        git.p4("sync")
        print("merging recent p4 changes into current branch")
        options["m"].Execute("p4/master")
        print("Changes in p4 not in master should now be in your current branch.")
        print("Review changes, tag versions (e.g. git tag -a v4.xx.xx, and then commit to master.")

        return True
