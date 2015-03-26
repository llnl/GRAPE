import pickle
import abc
import os
import grapeGit as git
import option
import utility
import grapeConfig


class Resumable(option.Option):
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        super(Resumable, self).__init__()
        self.progress = {}
        try:
            gitDir = git.gitDir()
            self.progressFile = os.path.join(gitDir, "grapeProgress")
        except git.GrapeGitError:
            # can happen if called from outside a workspace, create a .grapeProgress file
            # in the user's $HOME directory
            self.progressFile = os.path.join(os.path.expanduser('~'), ".grapeProgress")

    def dumpProgress(self, args,msg=""):
        print(msg)
        self._saveProgress(args)
        args["--continue"] = True
        self.progress["args"] = args
        self.progress["config"] = grapeConfig.grapeConfig()
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
    
    def _removeProgressFile(self):
        #remove the file
        try:
            os.remove(self.progressFile)
        except OSError as e:
            if e.errno == 2: 
                pass
            else:
                raise e

    @abc.abstractmethod
    def _resume(self, args, deleteProgressFile=True):
        try:
            self._readProgressFile()
        except IOError:
            # give the workspace level progress file a shot
            try:
                self.progressFile = os.path.join(utility.workspaceDir(), ".git", "grapeProgress")
                self._readProgressFile()
            except IOError as e:
                try:
                    # look for it at the home directory level
                    self.progressFile = os.path.join(os.path.expanduser('~'), ".grapeProgress")
                    self._readProgressFile()
                except:
                    utility.printMsg("No progress file found to continue from. Please enter a command without the "
                                     "--continue option. ")
                    raise e
        newArgs = self.progress["args"]
        #overwrite args with the loaded args
        for key in newArgs.keys():
            args[key] = newArgs[key]
        #load the config
        grapeConfig.resetGrapeConfig(self.progress["config"])
        if deleteProgressFile:
            self._removeProgressFile()
