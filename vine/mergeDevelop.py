import os
import ConfigParser
import grapeGit as git
import grapeMenu
import grapeConfig
import resumable
import utility


# pull and merge in an up-to-date development branch
class MergeDevelop(resumable.Resumable):
    """
    grape md  (Merge Down)
    merge changes from a public branch into your current topic branch
    If executed on a public branch, performs a pull --rebase to update your local public branch. 
    Usage: grape-md [--public=<branch>]
                    [--am | --as | --at | --ay]
                    [--continue]
                    [--recurse | --norecurse]
                    [-v]

    Options:
        --public=<branch>       Overrides the public branch to merge from. 
                                Default behavior is to merge according to 
                                .grapeconfig.flow.topicPrefixMappings.
        --am                    Perform the merge using git's default strategy.
        --as                    Perform the merge issuing conflicts on any file modified by both branches.
        --at                    Perform the merge resolving conficts using the public branch's version. 
        --ay                    Perform the merge resolving conflicts using your topic branch's version.
        --recurse               Perform merges in submodules first, then merge in the outer level keeping the
                                results of submodule merges.
        --norecurse             Do not perform merges in submodules, just attempt to merge the gitlinks.
        --continue              Resume the most recent call to grape md that issued conflicts in this workspace.
        -v                      Print out more git commands.


    """
    def __init__(self):
        super(MergeDevelop, self).__init__()
        self._key = "md"
        self._section = "Merge"

    @staticmethod
    def lookupPublicBranch():
        config = grapeConfig.grapeConfig()
        try:
            currentBranch = git.currentBranch(quiet=True)
        except git.GrapeGitError:
            return 'unknown'
        if currentBranch in config.get('flow', 'publicBranches'):
            return currentBranch
        try:
            branch = config.getPublicBranchFor(currentBranch)
        except KeyError:
            branchPrefix = git.branchPrefix(currentBranch)
            print("WARNING: prefix %s does not have an associated topic branch, nor is a default"
                  "public branch configured. \n"
                  "use --public=<branch> to define, or add %s:<branch> or ?:<branch> to \n"
                  "your .grapeconfig or .grapeuserconfig. " % (branchPrefix, branchPrefix))
            branch = None
        return branch

    def description(self):
        try: 
            currentBranch = git.currentBranch(quiet=True)
        except git.GrapeGitError:
            currentBranch = 'unknown'
        publicBranch = self.lookupPublicBranch()

        return "Merge latest changes on %s into %s" % (publicBranch, currentBranch)

    def mergeCurrentPublicBranch(self, args):
        try:
            git.pull("--rebase origin %s" % git.currentBranch(), quiet=not args["-v"])
        except git.GrapeGitError as e:
            # on conflict, ask user to resolve conflicts and then resume using grape md --continue
            if "conflict:" in e.gitOutput.lower():
                self.progress["stopPoint"] = "public rebase"
                self.dumpProgress(args)
                utility.printMsg("pull --rebase generated conflicts. Please resolve using git mergetool and then \n"
                      "continue by calling 'grape md --continue' .")
                return False
            else:
                print("GRAPE ERROR: pull --rebase failed for unknown reason")
                exit(1)
        return True

    def execute(self, args):

        quiet = not args["-v"]

        branch = args["--public"]
        if not branch:
            currentBranch = git.currentBranch(quiet)
            if currentBranch in grapeConfig.grapeConfig().get('flow', 'publicBranches'):
                return self.mergeCurrentPublicBranch(args)
            branch = grapeConfig.grapeConfig().getPublicBranchFor(git.currentBranch(quiet))
            if not branch:
                utility.printMsg("ERROR: public branches must be configured for grape md to work.")
        args["--public"] = branch
        # determine whether to merge in subprojects that have changed
        try:
            submodules = self.progress["submodules"]
        except KeyError:
            submodules = git.getModifiedSubmodules(branch, git.currentBranch(quiet), quiet)
            
        try:
            nested = self.progress["nested"]
        except KeyError:
            nested = grapeConfig.GrapeConfigParser.getAllModifiedNestedSubprojectPrefixes(branch)
                                                                                         
                                                                                         
        
        config = grapeConfig.grapeConfig()
        recurse = config.getboolean("workspace", "manageSubmodules") or args["--recurse"]
        recurse = recurse and (not args["--norecurse"]) and submodules
        args["--recurse"] = recurse

        # if we stored cwd in self.progress, make sure we end up there
        if "cwd" in self.progress:
            cwd = self.progress["cwd"]
        else:
            cwd = utility.workspaceDir()
        os.chdir(cwd)

        if "conflictedFiles" in self.progress:
            conflictedFiles = self.progress["conflictedFiles"]
        else:
            conflictedFiles = []
        # do an outer merge so long as we aren't recovering from a subproject conflict in a previous call
        if not ("stopPoint" in self.progress and "Subproject:" in self.progress["stopPoint"]):
            conflictedFiles = self.outerLevelMerge(args, branch)
        else:
            recurse = True
            
        # outerLevelMerge returns False if there was a non-conflict related issue
        if conflictedFiles is False:
            utility.printMsg("Initial merge failed. Resolve issue and try again. ")
            return False
        
        # merge nested subprojects
        for subproject in nested:
            if not self.mergeSubproject(args, subproject, branch, nested, cwd, isSubmodule=False):
                # stop for user to resolve conflicts
                self.progress["nested"] = nested
                self.dumpProgress(args)
                os.chdir(cwd)
                return False
        os.chdir(cwd)
        # merge submodules        
        if recurse:
            if len(submodules) > 0: 
                subBranchMappings = config.getMapping("workspace", "submoduleTopicPrefixMappings")
                subPublic = subBranchMappings[git.branchPrefix(branch)]
                
                for submodule in submodules:
                    if submodule in conflictedFiles or ("stopPoint" in self.progress and
                                                        submodule in self.progress["stopPoint"]):
                        if not self.mergeSubproject(args, submodule, subPublic, submodules, cwd, isSubmodule=True):
                            # stop for user to resolve conflicts
                            self.progress["conflictedFiles"] = conflictedFiles
                            self.dumpProgress(args)
                            return False
                os.chdir(cwd)
                conflictedFiles = git.conflictedFiles()
                # now that we resolved the submodule conflicts, continue the outer level merge 
                if len(conflictedFiles) == 0:
                    mergeArgs = args
                    mergeArgs["--continue"] = True
                    mergeArgs["--quiet"] = True
                    grapeMenu.menu().getOption("m").execute(mergeArgs)
                    conflictedFiles = git.conflictedFiles()

        if conflictedFiles:
            self.progress["stopPoint"] = "resolve conflicts"
            self.progress["cwd"] = cwd
            self.dumpProgress(args, "GRAPE: Outer level merge generated conflicts. Please resolve using git mergetool "
                                    "and then \n continue by calling 'grape md --continue' .")
            return False
        else:
            return grapeMenu.menu().applyMenuChoice("runHook", ["post-merge", '0', "--noExit"])


    def mergeSubproject(self, args, subproject, subPublic, subprojects, cwd, isSubmodule=True):
        # if we did this merge in a previous run, don't do it again
        try:
            if self.progress["Subproject: %s" % subproject] == "finished":
                return True
        except KeyError:
            pass
        os.chdir(os.path.join(git.baseDir(), subproject))
        mergeArgs = args
        mergeArgs["<branch>"] = subPublic
        print("GRAPE: Merging %s into %s for submodule %s" % (subPublic, git.currentBranch(), subproject))
        ret = grapeMenu.menu().getOption("m").execute(mergeArgs)
        conflict = not ret
        if conflict:
            self.progress["stopPoint"] = "Subproject: %s" % subproject
            subprojectKey = "submodules" if isSubmodule else "nested"
            self.progress[subprojectKey] = subprojects
            self.progress["cwd"] = cwd
            utility.printMsg("Merge in subproject %s failed. You likely need to resolve conflicts (git mergetool)\n"
                             " or stash/commit your current changes before doing the merge.\n"
                             "Continue by calling grape md --continue." % subproject)
            return False
        # if we are resuming from a conflict, the above grape m call would have taken care of continuing.
        # clear out the --continue flag.
        args["--continue"] = False
        # stage the updated submodule
        os.chdir(cwd)
        if isSubmodule:
            git.add(subproject, quiet=True)
        self.progress["Submodule: %s" % subproject] = "finished"
        return True

    @staticmethod
    def outerLevelMerge(args, branch):
        print("Merging changes from %s into your current branch..." % branch)
        mergeArgs = args
        mergeArgs["<branch>"] = branch
        mergeArgs["--quiet"] = True
        conflict = not grapeMenu.menu().getOption("mr").execute(mergeArgs)
        if conflict:
            conflictedFiles = git.conflictedFiles()
            if conflictedFiles:
                return conflictedFiles
            else:
                utility.printMsg("Merge issued error, but no conflicts. Aborting...")
                return False
        else:
            return []

    def setDefaultConfig(self, config):
        try:
            config.add_section("flow")
        except ConfigParser.DuplicateSectionError:
            pass
        config.set("flow", "publicBranches", "develop master")
        config.set("flow", "topicPrefixMappings", "?:develop")
        config.set("flow", "topicDestinationMappings", "none")

    def _resume(self, args):
        super(MergeDevelop, self)._resume(args)
        if self.progress["stopPoint"] == "public rebase":
            # recover from conflicts by continuing the rebase
            git.rebase("--continue", not args["-v"])
            return True

        return self.execute(args)

    def _saveProgress(self, args):
        super(MergeDevelop, self)._saveProgress(args)
