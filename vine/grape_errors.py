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

    def __getinitargs__(self):
        return (self.msg, self.code, self.gitOutput, self.gitCommand, self.cwd)

    def __str__(self):
        return "\nWORKING DIR: " + self.cwd + "\nCODE: " + str(self.code) + \
               '\nCMD: ' + self.gitCommand + '\nOUTPUT: ' + self.gitOutput

    def __repr__(self):
        return self.__str__()
