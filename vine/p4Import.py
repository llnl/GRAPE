import option

#imports recent changes in perforce into a hotfix branch ready for tagging and merging to master
class P4Import(option.Option):
    def __init__(self):
        self._key = "p4import"
        self._section = "Perforce Integration"

    def description(self):
        return "Import recent p4 changes into a hotfix branch"

    def execute(self,args):
        print("calling Grape hot")
        proceed = options['hot'].execute()
        assert proceed == True
        print("importing recent p4 changes into p4 master...")
        git.p4("sync")
        print("merging recent p4 changes into current branch")
        options["m"].execute("p4/master")
        print("Changes in p4 not in master should now be in your current branch.")
        print("Review changes, tag versions (e.g. git tag -a v4.xx.xx, and then commit to master.")

        return True
