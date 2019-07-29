import logging
import os


class GrapeGitError(Exception):

    def __init__(self, errmsg='', returnCode=-1, gitOutput='', gitCommand='',
                 cwd=os.getcwd()):
        """Arguments must be kept as keywords to allow pickling"""
        super(GrapeGitError, self).__init__()
        self.msg = errmsg
        self.code = returnCode
        self.gitOutput = gitOutput
        self.gitCommand = gitCommand
        self.commError = bool(
            self.code == 128 and "fatal: " in self.gitOutput and \
            ("Could not read from remote" in self.gitOutput or
             "unable to access" in self.gitOutput or
             "remote end hung up unexpectedly" in self.gitOutput))
        self.cwd = cwd
        logging.debug(repr(self), exc_info=True)

    def __getinitargs__(self):
        return (self.msg, self.code, self.gitOutput, self.gitCommand, self.cwd)

    def __str__(self):
        return "\nWORKING DIR: " + self.cwd + "\nCODE: " + str(self.code) + \
               '\nCMD: ' + self.gitCommand + '\nOUTPUT: ' + self.gitOutput

    def __repr__(self):
        return self.__str__()


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
        return "MRE with \n exceptions: %s \nrepos: %s\n branches: %s\n args: %s" % (
                self._exceptions, self._repos, self._branches, self._args)


class NoWorkspaceDirException(Exception):
    def __init__(self, cwd=''):
        self.cwd = cwd
        if cwd:
            self.message = "No .git found in %s" % cwd
        else:
            self.message = "No .git found"
        logging.error(self.message)
