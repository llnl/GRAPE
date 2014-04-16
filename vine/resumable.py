import pickle
import abc
import os
import grapeGit as git
import grapeMenu
import option

class Resumable(option.Option):
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        self.progress = {}
        self.progressFile = os.path.join(git.baseDir(), ".git", "grapeProgress")

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

    @abc.abstractmethod
    def _resume(self, args):
        with open(self.progressFile,'r') as f:
            p = pickle.Unpickler(f)
            self.progress = p.load()
        newArgs = self.progress["args"]
        #overwrite args with the loaded args
        for key in newArgs.keys():
            args[key] = newArgs[key]
        #remove the file
        os.remove(self.progressFile)
