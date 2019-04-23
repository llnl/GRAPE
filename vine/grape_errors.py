import os


class GrapeGitError(Exception):

    def __init__(self, errmsg='', returnCode=-1, gitOutput='', gitCommand='',
                 cwd=os.getcwd()):
        """Arguments must be kept as keywords to allow pickling"""
        super(GrapeGitError, self).__init__()
        self.msg = errmsg
        self.code = returnCode
        self.gitOutput = str(gitOutput)
        self.gitCommand = gitCommand
        if self.code == 128 and "fatal: " in self.gitOutput:
            if "Could not read from remote" in self.gitOutput or \
                    "unable to access" in self.gitOutput or \
                    "remote end hung up unexpectedly" in self.gitOutput:
                self.commError = True
            else:
                self.commError = False
        else:
            self.commError = False
        self.cwd = cwd

    def __getinitargs__(self):
        return (self.msg, self.code, self.gitOutput, self.gitCommand, self.cwd)

    def __str__(self):
        NL = "\n"
        return f"{NL}WORKING DIR: {self.cwd}{NL}CODE: {self.code}{NL}" + \
               f"CMD: {self.gitCommand}{NL}OUTPUT: {self.gitOutput}"

    def __repr__(self):
        return self.__str__()


# TODO: is pickle bug still a problem in Python 3.x?
# there is a bug in pickle that causes it to only use a default initializer for GrapeGitError objects,
# this is a wrapper to allow exception capture in runCommandOnRepoBranch.
class MultiRepoException(Exception):
    def __init__(self):
        self._exceptions = []
        self._repos = []
        self._branches = []
        self._args = []

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
        NL = "\n"
        return f"MRE with{NL} exceptions: {self._exceptions}{NL} repos: " + \
               f"{self._repos}{NL} branches: {self._branches}{NL} args: " + \
               f"{self._args}"


class NoWorkspaceDirException(Exception):
    def __init__(self, cwd=''):
        self.cwd = cwd
        if cwd:
            self.message = f"No .git found in {cmd}"
        else:
            self.message = "No .git found"
