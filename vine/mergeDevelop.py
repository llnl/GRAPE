import option,merge 
import ConfigParser
import grapeGit as git
import grapeConfig
import utility
# pull and merge in an up-to-date development branch
class MergeDevelop(option.Option):
    """
    grape md  (Merge Down)
    merge changes from a public branch into your current topic branch
    If executed on a public branch, performs a pull --rebase to update your local public branch. 
    Usage: grape-md [--public=<branch>] [--mappings=<pairs>] [--am | --as | --at | --ay]  

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


    """
    def __init__(self):
        self._key = "md"
        self._section = "Merge"

    def description(self):
        return "Merge latest changes on develop into your current feature branch"

    def execute(self,args):
        branch = args["--public"]
        if not branch:
            currentBranch = git.currentBranch()
            if currentBranch in grapeConfig.grapeConfig().get('flow','publicBranches'):
                git.pull("--rebase origin %s" % currentBranch) 
                return True
            branchPrefix = currentBranch.split('/')[0]
            prefixMappings = utility.parseConfigPairList(args["--mappings"])
            try: 
                branch = prefixMappings[branchPrefix]
            except KeyError:
                try: 
                    branch = prefixMappings['?']
                    print("WARNING: prefix %s does not have an associated topic branch. \n" 
                          "         using the default branch of %s" % (branchPrefix,branch) )
                except KeyError:    
                    print("prefix %s does not have an associated topic branch. \n" 
                          "use --public=<branch> to define, or add %s:<branch> to \n" 
                          "your .grapeconfig or .grapeuserconfig. " % (branchPrefix,branchPrefix))
                    exit(1)
        print("Merging changes from %s into your current branch..." % branch)
        strategy = None
        if args['--am']:
            strategy = 'am'
        elif args['--as']: 
            strategy = 'as' 
        elif args['--at']: 
            strategy = 'at'
        elif args['--ay']: 
            strategy = 'ay'
        if not merge.mergeIntoCurrent(".", branch,strategy):
            return False
        return True

    def setDefaultConfig(self,config):
        try:
            config.add_section("flow")
        except ConfigParser.DuplicateSectionError:
            pass
        config.set("flow","publicBranches","develop master")
        config.set("flow","topicPrefixMappings","?:develop")

        
