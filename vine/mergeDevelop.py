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
    Usage: grape-md [--public=<branch>] [--subpublic=<branch>]
                    [--am | --as | --at | --ay]
                    [--continue]
                    [--recurse | --noRecurse]
                    [--noUpdate]
                    

    Options:
        --public=<branch>       Overrides the public branch to merge from. 
                                Default behavior is to merge according to 
                                .grapeconfig.flow.topicPrefixMappings.
        --subpublic=<branch>    Overrides the submodules' public branch to merge from. Default behavior is to merge
                                according to .grapeconfig.flow.submoduleTopicPrefixMappings. 
        --am                    Perform the merge using git's default strategy.
        --as                    Perform the merge issuing conflicts on any file modified by both branches.
        --at                    Perform the merge resolving conficts using the public branch's version. 
        --ay                    Perform the merge resolving conflicts using your topic branch's version.
        --recurse               Perform merges in submodules first, then merge in the outer level keeping the
                                results of submodule merges.
        --noRecurse             Do not perform merges in submodules, just attempt to merge the gitlinks.
        --continue              Resume the most recent call to grape md that issued conflicts in this workspace.
        --noUpdate              Do not update local versions of the public branch before attempting merges. 
        


    """
    def __init__(self):
        super(MergeDevelop, self).__init__()
        self._key = "md"
        self._section = "Merge"

    @staticmethod
    def lookupPublicBranch():
        config = grapeConfig.grapeConfig()
        try:
            currentBranch = git.currentBranch()
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
                  "[flow].publicBranches in your .grapeconfig or .git/.grapeuserconfig. " % (branchPrefix, branchPrefix))
            branch = None
        return branch

    def description(self):
        try: 
            currentBranch = git.currentBranch()
        except git.GrapeGitError:
            currentBranch = 'unknown'
        publicBranch = self.lookupPublicBranch()

        return "Merge latest changes on %s into %s" % (publicBranch, currentBranch)


    def execute(self, args):
        if not "<<cmd>>" in args:
            args["<<cmd>>"] = "md"
        branch = args["--public"]
        if not branch:
            currentBranch = git.currentBranch()
            branch = grapeConfig.grapeConfig().getPublicBranchFor(git.currentBranch())
            if not branch:
                utility.printMsg("ERROR: public branches must be configured for grape md to work.")
        args["--public"] = branch
        # determine whether to merge in subprojects that have changed
        try:
            submodules = self.progress["submodules"]
        except KeyError:
            modifiedSubmodules = git.getModifiedSubmodules(branch, git.currentBranch())
            activeSubmodules = git.getActiveSubmodules()
            submodules = [sub for sub in modifiedSubmodules if sub in activeSubmodules]

        try:
            nested = self.progress["nested"]
        except KeyError:
            nested = grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes()
                                                                                         
                                                                                         
        
        config = grapeConfig.grapeConfig()
        recurse = config.getboolean("workspace", "manageSubmodules") or args["--recurse"]
        recurse = recurse and (not args["--noRecurse"]) and len(submodules) > 0
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

        # checking for a consistent workspace before doing a merge
        utility.printMsg("Checking for a consistent workspace before performing merge...")
        ret = grapeMenu.menu().applyMenuChoice("status", ['--failIfInconsistent'])
        if ret is False:
            utility.printMsg("Workspace inconsistent! Aborting attempt to do the merge. Please address above issues and then try again.")
            return False
            

        if not "updateLocalDone" in self.progress and not args["--noUpdate"]:
            # make sure public branches are to date in outer level repo.
            utility.printMsg("Calling grape up to ensure topic and public branches are up-to-date. ")
            grapeMenu.menu().applyMenuChoice('up', ['up','--public=%s' % args["--public"],'--noRecurse'])  
            self.progress["updateLocalDone"] = True
        
        # do an outer merge if we haven't done it yet        
        if not "outerLevelDone" in self.progress:
            self.progress["outerLevelDone"] = False
        if not self.progress["outerLevelDone"]:
            conflictedFiles = self.outerLevelMerge(args, branch)
            
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
                if args["--subpublic"]:
                    subPublic = args["--subpublic"]
                else:
                    subBranchMappings = config.getMapping("workspace", "submoduleTopicPrefixMappings")
                    subPublic = subBranchMappings[git.branchPrefix(branch)]
                for submodule in submodules:
                    if not self.mergeSubproject(args, submodule, subPublic, submodules, cwd, isSubmodule=True):
                        # stop for user to resolve conflicts
                        self.progress["conflictedFiles"] = conflictedFiles
                        self.dumpProgress(args)
                        return False
                os.chdir(cwd)
                conflictedFiles = git.conflictedFiles()
                # now that we resolved the submodule conflicts, continue the outer level merge 
                if len(conflictedFiles) == 0:
                    self.continueLocalMerge(args)
                    conflictedFiles = git.conflictedFiles()

        if conflictedFiles:
            self.progress["stopPoint"] = "resolve conflicts"
            self.progress["cwd"] = cwd
            self.dumpProgress(args, "GRAPE: Outer level merge generated conflicts. Please resolve using git mergetool "
                                    "and then \n continue by calling 'grape md --continue' .")
            return False
        else:
            grapeMenu.menu().applyMenuChoice("runHook", ["post-merge", '0', "--noExit"])
        return True

    def mergeSubproject(self, args, subproject, subPublic, subprojects, cwd, isSubmodule=True):
        # if we did this merge in a previous run, don't do it again
        try:
            if self.progress["Subproject: %s" % subproject] == "finished":
                return True
        except KeyError:
            pass
        os.chdir(os.path.join(git.baseDir(), subproject))
        mergeArgs = args.copy()
        mergeArgs["--public"] = subPublic

        utility.printMsg("Merging %s into %s for %s %s" % 
                         (subPublic, git.currentBranch(), "submodule" if isSubmodule else "subproject", subproject))
        git.fetch("origin")
        # update our local reference to the remote branch so long as it's fast-forwardable or we don't have it yet..)
        hasRemote = git.hasBranch("origin/%s" % subPublic)
        hasBranch = git.hasBranch(subPublic)
        if  hasRemote and  (git.branchUpToDateWith(subPublic, "origin/%s" % subPublic) or not hasBranch):
            git.fetch("origin %s:%s" % (subPublic, subPublic))
        ret = self.mergeIntoCurrent(subPublic, mergeArgs)
        conflict = not ret
        if conflict:
            self.progress["stopPoint"] = "Subproject: %s" % subproject
            subprojectKey = "submodules" if isSubmodule else "nested"
            self.progress[subprojectKey] = subprojects
            self.progress["cwd"] = cwd
            conflictedFiles = git.conflictedFiles()
            if conflictedFiles:
                if isSubmodule: 
                    typeStr = "submodule"
                else:
                    typeStr = "nested subproject"
                
                utility.printMsg("Merge in %s %s from %s to %s issued conflicts. Resolve and commit those changes \n"
                                 "using git mergetool and git commit in the submodule, then continue using grape\n"
                                 "%s --continue" % (typeStr, subproject, subPublic, git.currentBranch(), args["<<cmd>>"]))
            else:
                utility.printMsg("Merge in %s failed for an unhandled reason. You may need to stash / commit your current\n"
                                 "changes before doing the merge. Inspect git output above to troubleshoot. Continue using\n"
                                 "grape %s --continue." % (subproject, args["<<cmd>>"]))
            return False
        # if we are resuming from a conflict, the above grape m call would have taken care of continuing.
        # clear out the --continue flag.
        args["--continue"] = False
        # stage the updated submodule
        os.chdir(cwd)
        if isSubmodule:
            git.add(subproject)
        self.progress["Subproject: %s" % subproject] = "finished"
        return True

    def outerLevelMerge(self, args, branch):
        utility.printMsg("Merging changes from %s into your current branch..." % branch)
              
        conflict = not self.mergeIntoCurrent(branch, args)

        if conflict:
            conflictedFiles = git.conflictedFiles()
            if conflictedFiles:
                return conflictedFiles
            else:
                utility.printMsg("Merge issued error, but no conflicts. Aborting...")
                return False
        else:
            self.progress["outerLevelDone"] = True
            return []

    def merge(self, branch, strategy, args):
        try:
            git.merge("%s %s" % (branch, strategy))
            return True
        except git.GrapeGitError as error:
            print error.gitOutput
            if "conflict" in error.gitOutput.lower():
                utility.printMsg("Conflicts generated. Resolve using git mergetool, then continue "
                                  "with grape %s --continue. " % args["<<cmd>>"])
            else:
                print("Merge command %s failed. Quitting." % error.gitCommand)
            return False

    def continueLocalMerge(self, args):
        status = git.status()
        if "All conflicts fixed but you are still merging." in status:
            git.commit("-m \"GRAPE: merge from %s after conflict resolution.\"" % args["--public"])
            return True
        elif git.isWorkingDirectoryClean():
            return False
        else:
            return False

    def mergeIntoCurrent(self, branchName, args):
        updateArgs = ['up', '--wd=%s' % os.getcwd(), '--noRecurse', '--public=%s' % branchName]
        if not args["--noUpdate"]:
            grapeMenu.menu().applyMenuChoice('up', updateArgs)
        choice = False
        strategy = None
        if args["--continue"]:
            if self.continueLocalMerge(args):
                return True
        if args['--am']:
            strategy = 'am'
        elif args['--as']: 
            strategy = 'as' 
        elif args['--at']: 
            strategy = 'at'
        elif args['--ay']: 
            strategy = 'ay'
    
        if not strategy: 
            strategy = utility.userInput("How do you want to resolve changes? [am / as / at / ay ] \n" +
                                         "am: Auto Merge (default) \n" +
                                         "as: Safe Merge - issues conflicts if both branches touch same file.\n" +
                                         "at: Accept Theirs - resolves conflicts by accepting changes in %s\n" %
                                         branchName + "ay: Accept Yours - resolves conflicts by using changes "
                                                      "in current branch.", "am")
    
        if strategy == 'am':
            args["--am"] = True
            utility.printMsg("Merging using git's default strategy...")
            choice = self.merge(branchName, "", args)
        elif strategy == 'as':
            args["--as"] = True
            # this employs using the custom low-level merge driver "verify" and
            # appending a "* merge=verify" to the .gitattributes file.
            #
            # see
            # http://stackoverflow.com/questions/5074452/git-how-to-force-merge-conflict-and-manual-merge-on-selected-file
            # for details.
            utility.printMsg("Merging forcing conflicts whenever both branches edited the same file...")
            base = git.gitDir()
            if base == "":
                return False
            attributes = os.path.join(base, ".gitattributes")
            tmpattributes = None
            if os.path.exists(attributes): 
                tmpattributes = os.path.join(base, ".gitattributes.tmp")
                # save original attributes file
                shutil.copyfile(attributes, tmpattributes)
                #append merge driver strategy to the attributes file
                with open(attributes, 'a') as f:
                    f.write("* merge=verify")
            else: 
                with open(attributes, 'w') as f:
                    f.write("* merge=verify")
    
            # perform the merge
            choice = self.merge(branchName, "", args)
    
            # restore original attributes file
            if tmpattributes:
                shutil.copyfile(tmpattributes, attributes)
                os.remove(tmpattributes)
            else:
                os.remove(attributes)
    
        elif strategy == 'at':
            args["--at"] = True
            utility.printMsg("Merging using recursive strategy, resolving conflicts cleanly with changes in %s..." % branchName)
            choice = self.merge(branchName, "-Xtheirs", args)
    
        elif strategy == 'ay':
            args["--ay"] = True
            utility.printMsg("Merging using recursive strategy, resolving conflicts cleanly with current branch's changes...")
            choice = self.merge(branchName, "-Xours", args)
    
        return choice

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
            git.rebase("--continue")
            retval = True
        else:
            retval = self.execute(args)
        return retval

    def _saveProgress(self, args):
        super(MergeDevelop, self)._saveProgress(args)
        # this lets grape m know that the --continue is for grape md to resume...
        self.progress["inMD"] = True
