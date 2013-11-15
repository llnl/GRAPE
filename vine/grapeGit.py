import utility


class GrapeGit(): 
    def dir(self): 
        process = utility.executeSubProcess("git rev-parse --show-toplevel", os.getcwd(), subprocess.PIPE)
        if process.returncode != 0:
            print("Error: Could not determine top level git directory.")
            return ""
        output = process.communicate()[0]
        return output.strip()        

    def mergeAbort(self): 
        process = utility.executeSubProcess("git merge --abort", os.getcwd())
        if process.returncode != 0:
            print("Error: Could not determine top level git directory.")
            return False        

    def mergeIntoCurrent(self,repoName,branchName):
        self.fetch(repoName,branchName)
        choice = None
        strategy = utility.userInput("How do you want to resolve changes? [am / as / at / ay ] \n"+
                             "am: Auto Merge (default) \n"+
                             "as: Safe Merge - issues conflicts if both branches touch same file.\n" +
                             "at: Accept Theirs - resolves conflicts by accepting changes in %s\n" % branchName+
                             "ay: Accept Theirs - resolves conflicts by using changes in current branch." ,"am")


        if (strategy == 'am'):
            print("merging using git's default strategy")
            git.pull(repoName,branchName)
        elif (strategy == 'as'):
            # this employs using the custom low-level merge driver "verify" and
            # appending a "* merge=verify" to the .gitattributes file.
            #
            # see http://stackoverflow.com/questions/5074452/git-how-to-force-merge-conflict-and-manual-merge-on-selected-file for details.
            print("merging forcing conflicts whenever both branches edited the same file...")
            base = utility.gitDir()
            if base == "":
                return False
            attributes = os.path.join(base,".gitattributes")
            tmpattributes = os.path.join(base,".gitattributes.tmp")
            # save original attributes file
            shutil.copyfile(attributes,tmpattributes)
            #append merge driver strategy to the attributes file
            with open(attributes,'a') as f:
                f.write("* merge=verify")

            # perform the merge
            choice = gitMerge(repoName, branchName)

            # restore original attributes file
            shutil.copyfile(tmpattributes,attributes)
            os.remove(tmpattributes)

        elif (strategy == 'at'):
            print("merging using recursive strategy, resolving conflicts cleanly with %s's changes" % branchName)
            choice = gitMerge(repoName, branchName, "-Xtheirs")

        elif (strategy == 'ay'):
            print("merging using recursive strategy, resolving conflicts cleanly with current branch's changes")
            choice = gitMerge(repoName, branchName, "-Xours")

        if choice == None:
            return False
        choice = choice.strip().lower()
        if choice == "abort":
            if not gitMergeAbort():
                return False
        elif choice:
            return options[choice].execute()

        return True
