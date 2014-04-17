import pickle
import abc
import os
import grapeGit as git
import option
import utility


class Resumable(option.Option):
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        super(Resumable, self).__init__()
        self.progress = {}
        try:
            self.progressFile = os.path.join(git.gitDir(), "grapeProgress")
        except git.GrapeGitError:
            # can happen if called from outside a workspace, create a .grapeProgress file
            # in the user's $HOME directory
            self.progressFile = os.path.join(os.path.expanduser('~'), ".grapeProgress")

    def dumpProgress(self, args):
        self._saveProgress(args)
        args["--continue"] = True
        self.progress["args"] = args
        with open(self.progressFile,'w') as f:
            p = pickle.Pickler(f)
            p.dump(self.progress)

    @abc.abstractmethod
    def _saveProgress(self, args):
        pass

    def _readProgressFile(self):
        with open(self.progressFile, 'r') as f:
            p = pickle.Unpickler(f)
            self.progress = p.load()

    @abc.abstractmethod
    def _resume(self, args):
        try:
            self._readProgressFile()
        except IOError:
            # give the workspace level progress file a shot
            try:
                self.progressFile = os.path.join(utility.workspaceDir(), ".git", "grapeProgress")
                self._readProgressFile()
            except IOError:
                # look for it at the home directory level
                self.progressFile = os.path.join(os.path.expanduser('~'), ".grapeProgress")
                self._readProgressFile()
        newArgs = self.progress["args"]
        #overwrite args with the loaded args
        for key in newArgs.keys():
            args[key] = newArgs[key]
        #remove the file
        os.remove(self.progressFile)
