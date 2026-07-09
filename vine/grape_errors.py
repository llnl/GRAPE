import logging
import os


class GrapeGitError(Exception):

    def __init__(self, errmsg='', returnCode=-1, gitOutput='', gitCommand='',
                 cwd=os.getcwd()):
        """Arguments must be kept as keywords to allow pickling"""
        super(GrapeGitError, self).__init__()
        self.message = errmsg
        self.code = returnCode
        if isinstance(gitOutput, bytes):
            gitOutput = gitOutput.decode()
        self.gitOutput = gitOutput
        self.gitCommand = gitCommand
        self.lowerGitOutput = self.gitOutput.lower()
        if self.code == 128 and "fatal: " in self.lowerGitOutput:
            if "could not read from remote" in self.lowerGitOutput or \
                    "unable to access" in self.lowerGitOutput or \
                    "remote end hung up unexpectedly" in self.lowerGitOutput:
                self.commError = True
            else:
                self.commError = False
        else:
            self.commError = False
        self.authError = False
        if "authentication failed" in self.lowerGitOutput:
            self.authError = True
        self.cwd = cwd
        logging.debug(repr(self), exc_info=True)

    def __str__(self):
        return f"\nWORKING DIR: {self.cwd}\nCODE: {self.code}\n" + \
               f"CMD: {self.gitCommand}\nOUTPUT: {self.gitOutput}\n" + \
               f"STDERR: {self.message}"

    def __repr__(self):
        return self.__str__()

    def could_not_find_remote_ref(self):
        return "couldn't find remote ref" in self.gitOutput.lower()

    def has_conflict(self):
        return "conflict" in self.gitOutput.lower()


class GrapeGitIndexLockError(GrapeGitError):
    """Raised when git cannot create an index.lock file.

    Attributes:
        indexLockPath: Path to the lock file reported by git.
        index_lock_path: Alias for indexLockPath for snake_case callers.
    """

    def __init__(self, errmsg='', returnCode=-1, gitOutput='',
                 gitCommand='', cwd=os.getcwd(), indexLockPath=''):
        """Initializes a git index lock error.

        Args:
            errmsg: Human-readable error summary.
            returnCode: Exit code from the git command.
            gitOutput: Captured stdout and stderr from the git command.
            gitCommand: Full git command that failed.
            cwd: Working directory where the git command ran.
            indexLockPath: Path to the lock file reported by git.

        Note:
            Arguments must be kept as keywords to allow pickling.
        """
        super(GrapeGitIndexLockError, self).__init__(
            errmsg=errmsg, returnCode=returnCode, gitOutput=gitOutput,
            gitCommand=gitCommand, cwd=cwd)
        self.indexLockPath = indexLockPath
        self.index_lock_path = indexLockPath


# there is a bug in pickle that causes it to only use a default initializer for GrapeGitError objects,
# this is a wrapper to allow exception capture in runCommandOnRepoBranch.
class MultiRepoException(Exception):
    def __init__(self, workspace_dir):
        self._exceptions = []
        self._repos = []
        self._branches = []
        self._args = []
        self._remote_urls = []
        self.workspace_dir = workspace_dir
        logging.debug(repr(self))

    def addException(self, e, repo, branch, args, remote_url):
        self._exceptions.append(e)
        self._repos.append(repo)
        self._branches.append(branch)
        self._args.append(args)
        self._remote_urls.append(remote_url)

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

    def remote_urls(self):
        return self._remote_urls

    def __repr__(self):
        return f"MRE with\n exceptions: {self._exceptions}\n repos: " + \
               f"{self._repos}\n branches: {self._branches}\n args: " + \
               f"{self._args} \n remote_urls: {self._remote_urls}"


class NoWorkspaceDirException(Exception):
    def __init__(self, cwd=''):
        self.cwd = cwd
        if cwd:
            self.message = f"No .git found in {cwd}"
        else:
            self.message = "No .git found"
        logging.error(self.message)
