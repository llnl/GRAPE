import option,merge 
import ConfigParser
import grapeGit as git
import grapeMenu
import grapeConfig
import resumable
# pull and merge in an up-to-date development branch
class MergeDevelop(resumable.Resumable):
    """
    grape md  (Merge Down)
    merge changes from a public branch into your current topic branch
    If executed on a public branch, performs a pull --rebase to update your local public branch. 
    Usage: grape-md [--public=<branch>] [--mappings=<pairs>] [--am | --as | --at | --ay] [--continue]

    Options:
        --public=<branch>       Overrides the public branch to merge from. 
                                Default behavior is to merge according to 
                                flow.topicPrefixMappings. 
        --mappings=<pairs>      Defines the prefix to branch mappings to determine which public
                                branch to merge from, e.g. "feature:develop hotfix:master". 
                                [default: .grapeconfig.flow.topicPrefixMappings]
        --am                    Perform the merge using git's default strategy. 
        --as                    Perform the merge issuing conflicts on any file modified by both branches.
        --at                    Perform the merge resolving conficts using the public branch's version. 
        --ay                    Perform the merge resolving conflicts using your topic branch's version.
        --continue              Resume from a previous call to grape md, typically after resolving a conflict.


    """
    def __init__(self):
        super(MergeDevelop, self).__init__()
        self._key = "md"
        self._section = "Merge"


    def lookupPublicBranch(self,mappings):
        try:
            currentBranch = git.currentBranch(quiet=True)
        except:
            return 'unknown'
        if currentBranch in grapeConfig.grapeConfig().get('flow','publicBranches'):
            return currentBranch
        branchPrefix = currentBranch.split('/')[0]
        prefixMappings = grapeConfig.parseConfigPairList(mappings)
        try: 
            branch = prefixMappings[branchPrefix]
        except KeyError:
            print("WARNING: prefix %s does not have an associated topic branch, nor is a default"
                  "public branch configured. \n"
                  "use --public=<branch> to define, or add %s:<branch> or ?:<branch> to \n"
                  "your .grapeconfig or .grapeuserconfig. " % (branchPrefix, branchPrefix))
            branch = None
        return branch
           
    
    def description(self):
        try: 
            currentBranch = git.currentBranch(quiet=True)
        except:
            currentBranch = 'unknown'
        publicBranch = self.lookupPublicBranch(grapeConfig.grapeConfig().get('flow','topicPrefixMappings'))

        return "Merge latest changes on %s into %s" % (publicBranch, currentBranch)

    def execute(self, args):



        branch = args["--public"]
        if not branch:
            currentBranch = git.currentBranch()
            if currentBranch in grapeConfig.grapeConfig().get('flow','publicBranches'):
                try:
                    output = git.pull("--rebase origin %s" % currentBranch)
                except git.GrapeGitError as e:
                    # on conflict, ask user to resolve conflicts and then resume using grape md --continue
                    if "conflict:" in e.gitOutput.lower():

                        self.progress["stopPoint"] = "public rebase"
                        self.dumpProgress(args)
                        print("GRAPE: pull --rebase generated conflicts. Please resolve using git mergetool and then \n"
                              "continue by calling 'grape md --continue' .")
                        return False
                    else:
                        print("GRAPE ERROR: pull --rebase failed for unknown reason")
                        exit(1)
                except:
                    return False
                return True
            branch = self.lookupPublicBranch(args["--mappings"])
            if not branch:
                print("GRAPE ERROR: public branch must be configured for grape md to work.")

        print("Merging changes from %s into your current branch..." % branch)

        mergeArgs = args
        mergeArgs["<branch>"] = branch
        conflict = not grapeMenu.menu().getOption("m").execute(mergeArgs)
        if conflict:
            self.progress["stopPoint"] = "outer level merge"
            args["--public"] = branch
            self.dumpProgress(args)
            print("GRAPE: merge generated conflicts. Please resolve using git mergetool and then \n"
                              "continue by calling 'grape md --continue' .")
            return False
        return True

    def setDefaultConfig(self,config):
        try:
            config.add_section("flow")
        except ConfigParser.DuplicateSectionError:
            pass
        config.set("flow", "publicBranches", "develop master")
        config.set("flow", "topicPrefixMappings", "?:develop")

    def _resume(self, args):
        super(MergeDevelop, self)._resume(args)
        if self.progress["stopPoint"] == "public rebase":
            # recover from conflicts by continuing the rebase
            git.rebase("--continue")
            return True
        return self.execute(args)

    def _saveProgress(self, args):
        super(MergeDevelop, self)._saveProgress(args)

