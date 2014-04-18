import os
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
                    [--recurse | --norecurse]

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
        --recurse               Perform merges in submodules first, then merge in the outer level keeping the
                                results of submodule merges.
        --norecurse             Do not perform merges in submodules, just attempt to merge the gitlinks.
        --continue              Resume the most recent call to grape md that issued conflicts in this workspace.


    """
    def __init__(self):
        super(MergeDevelop, self).__init__()
        self._key = "md"
        self._section = "Merge"


    def lookupPublicBranch(self, mappings):
        try:
            currentBranch = git.currentBranch(quiet=True)
        except git.GrapeGitError:
            return 'unknown'
        if currentBranch in grapeConfig.grapeConfig().get('flow', 'publicBranches'):
            return currentBranch
        prefixMappings = grapeConfig.parseConfigPairList(mappings)
        branchPrefix = git.branchPrefix(currentBranch)
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
        except git.GrapeGitError:
            currentBranch = 'unknown'
        publicBranch = self.lookupPublicBranch(grapeConfig.grapeConfig().get('flow', 'topicPrefixMappings'))

        return "Merge latest changes on %s into %s" % (publicBranch, currentBranch)

    def mergeCurrentPublicBranch(self, args):
        try:
            git.pull("--rebase origin %s" % git.currentBranch())
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
        return True

    def execute(self, args):
        branch = args["--public"]
        if not branch:
            currentBranch = git.currentBranch()
            if currentBranch in grapeConfig.grapeConfig().get('flow', 'publicBranches'):
                return self.mergeCurrentPublicBranch(args)
            branch = self.lookupPublicBranch(args["--mappings"])
            if not branch:
                print("GRAPE ERROR: public branch must be configured for grape md to work.")
        args["--public"] = branch
        # determine whether to merge in submodules that have changed
        try:
            submodules = self.progress["submodules"]
        except KeyError:
            submodules = git.getModifiedSubmodules(branch, git.currentBranch())
        config = grapeConfig.grapeConfig()
        recurse = config.get("workspace", "manageSubmodules").lower() == "true" or args["--recurse"]
        recurse = recurse and not args["--norecurse"] and submodules
        args["--recurse"] = recurse

        # if we stored cwd in self.progress, make sure we end up there
        if "cwd" in self.progress:
            cwd = self.progress["cwd"]
        else:
            cwd = git.baseDir()
        os.chdir(cwd)

        conflictedFiles = []
        # do an outer merge so long as we aren't recovering from a submodule conflict in a previous call
        if not ("stopPoint" in self.progress and "Submodule:" in self.progress["stopPoint"]):
            conflictedFiles = self.outerLevelMerge(args, branch)
        else:
            recurse = True
        if recurse:
            subBranchMappings = config.get("workspace", "submoduleTopicPrefixMappings")
            subBranchMappings = grapeConfig.parseConfigPairList(subBranchMappings)
            subPublic = subBranchMappings[git.branchPrefix(branch)]
            mergedSubmodules = []
            for submodule in submodules:
                if submodule in conflictedFiles or submodule in self.progress["stopPoint"]:
                    if self.mergeSubmodule(args, submodule, subPublic, submodules, cwd):
                        mergedSubmodules.append(submodule)
                    else:
                        return False
            #self.stageModifiedSubmodules(args, mergedSubmodules)
            os.chdir(cwd)
            conflictedFiles = git.conflictedFiles()
            if not conflictedFiles:
                mergeArgs = args
                mergeArgs["--continue"] = True
                grapeMenu.menu().getOption("m").execute(mergeArgs)
                conflictedFiles = git.conflictedFiles()

        if conflictedFiles:
            self.progress["stopPoint"] = "resolve conflicts"
            self.progress["cwd"] = cwd
            self.dumpProgress(args, "GRAPE: Outer level merge generated conflicts. Please resolve using git mergetool and then \n"
                                    "continue by calling 'grape md --continue' .")
            return False
        else:
            #git.commit("-m \"Merged %s into %s\"" % (branch, git.currentBranch()))
            grapeMenu.menu().applyMenuChoice("runHook", ["post-merge", '0'])
        return True

    def mergeSubmodule(self, args, subproject, subPublic, submodules, cwd):
        # if we did this merge in a previous run, don't do it again
        try:
            if self.progress["Submodule: %s" % subproject] == "finished":
                return True
        except KeyError:
            pass
        os.chdir(os.path.join(git.baseDir(), subproject))
        mergeArgs = args
        mergeArgs["<branch>"] = subPublic
        conflict = not grapeMenu.menu().getOption("m").execute(mergeArgs)
        if conflict:
            self.progress["stopPoint"] = "Submodule: %s" % subproject
            self.progress["submodules"] = submodules
            self.progress["cwd"] = cwd
            self.dumpProgress(args)
            print("GRAPE: merge in %s generated CONFLICT(S). Resolve using git mergetool and then \n"
                  "continue by calling 'grape md --continue'")
            return False
        # if we are resuming from a conflict, the above grape m call would have taken care of continuing.
        # clear out the --continue flag.
        args["--continue"] = False
        # stage the updated submodule
        os.chdir(cwd)
        git.add(subproject)
        self.progress["Submodule: %s" % subproject] = "finished"
        return True

    def stageModifiedSubmodules(self, args, submodules):
        if not submodules:
            return True
        try:
            git.checkout("--ours %s" % ' '.join(submodules))
        except git.GrapeGitError:
            self.progress["stopPoint"] = "submodule gitlink checkout"
            self.progress["submodules"] = submodules
            self.progress["cwd"] = os.getcwd()
            self.dumpProgress(args, "GRAPE: checkout of our version of submodule gitlinks failed.\n"
                                    "Perhaps a post-checkout hook issued an error?\n"
                                    "Once resolved, continue using grape md --continue.")
            return False
        try:
            git.add("%s" % ' '.join(submodules))
        except git.GrapeGitError:
            self.progress["stopPoint"] = "submodule gitlink add"
            self.progress["submodules"] = submodules
            self.progress["cwd"] = os.getcwd()
            self.dumpProgress(args,
                              "GRAPE: adding changed gitlinks failed for some reason. Resolve and then "
                              "continue using grape md --continue")

    def outerLevelMerge(self, args, branch):
        print("Merging changes from %s into your current branch..." % branch)
        mergeArgs = args
        mergeArgs["<branch>"] = branch
        mergeArgs["--quiet"] = True
        conflict = not grapeMenu.menu().getOption("m").execute(mergeArgs)
        if conflict:
            return git.conflictedFiles()
        else:
            return []

    def setDefaultConfig(self, config):
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
        #if self.progress["stopPoint"] == "submodule gitlink checkout" or \
        #                self.progress["stopPoint"] == "submodule gitlink add":
        #    os.chdir(self.progress["cwd"])
        #    return self.outerLevelMerge(args, args["--public"])

        if self.progress["stopPoint"] == "outer level merge":
            return self.outerLevelMerge(args, args["--public"])

        return self.execute(args)

    def _saveProgress(self, args):
        super(MergeDevelop, self)._saveProgress(args)