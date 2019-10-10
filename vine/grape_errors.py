import logging
import os


class GrapeGitError(Exception):

    def __init__(self, errmsg='', returnCode=-1, gitOutput='', gitCommand='',
                 cwd=os.getcwd()):
        """Arguments must be kept as keywords to allow pickling"""
        super(GrapeGitError, self).__init__()
        self.msg = errmsg
        self.code = returnCode
        if isinstance(gitOutput, bytes):
            gitOutput = gitOutput.decode()
        self.gitOutput = gitOutput
        self.gitCommand = gitCommand
        if self.code == 128 and "fatal: " in self.gitOutput.lower():
            if "could not read from remote" in self.gitOutput.lower() or \
                    "unable to access" in self.gitOutput.lower() or \
                    "remote end hung up unexpectedly" in self.gitOutput.lower():
                self.commError = True
            else:
                self.commError = False
        else:
            self.commError = False
        self.cwd = cwd
        logging.debug(repr(self), exc_info=True)

    def __str__(self):
        return f"\nWORKING DIR: {self.cwd}\nCODE: {self.code}\n" + \
               f"CMD: {self.gitCommand}\nOUTPUT: {self.gitOutput}\n" + \
               f"STDERR: {self.msg}"

    def __repr__(self):
        return self.__str__()

    def could_not_find_remote_ref(self):
        return "couldn't find remote ref" in self.gitOutput.lower()

    def has_conflict(self):
        return "conflict" in self.gitOutput.lower()


# there is a bug in pickle that causes it to only use a default initializer for GrapeGitError objects,
# this is a wrapper to allow exception capture in runCommandOnRepoBranch.
class MultiRepoException(Exception):
    def __init__(self):
        self._exceptions = []
        self._repos = []
        self._branches = []
        self._args = []
        logging.debug(repr(self))

    def addException(self, e, repo, branch, args):
        self._exceptions.append(e)
        self._repos.append(repo)
        self._branches.append(branch)
        self._args.append(args)

    def __getitem__(self, pos):
        return self._exceptions[pos]

    def exceptions(self):
        return self._exceptions

    def repos(self):
        return self._repos

    def branches(self):
        return self._branches

    def args(self):
        return self._args

    def hasException(self):
        return len(self._exceptions) > 0

    def __repr__(self):
        return f"MRE with\n exceptions: {self._exceptions}\n repos: " + \
               f"{self._repos}\n branches: {self._branches}\n args: " + \
               f"{self._args}"


class NoWorkspaceDirException(Exception):
    def __init__(self, cwd=''):
        self.cwd = cwd
        if cwd:
            self.message = f"No .git found in {cwd}"
        else:
            self.message = "No .git found"
        logging.error(self.message)
