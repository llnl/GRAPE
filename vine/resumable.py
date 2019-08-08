from abc import ABC, abstractmethod
import io
import logging
import os
import pickle
from vine import config_parser_global
from vine import grape_errors
from vine import grapeGit as git
from vine import utility
from vine import vine_logging


class Resumable(ABC):

    def __init__(self):
        super(Resumable, self).__init__()
        self.progress = {}
        try:
            gitDir = str(git.gitDir())
            self.progressFile = os.path.join(gitDir, "grapeProgress")
        except grape_errors.GrapeGitError:
            # can happen if called from outside a workspace, create a .grapeProgress file
            # in the user's $HOME directory
            self.progressFile = os.path.join(os.path.expanduser('~'), ".grapeProgress")

    def dumpProgress(self, args, msg=""):
        if msg:
            logging.info(msg)
        self._saveProgress(args)
        args["--continue"] = True
        self.progress["args"] = args
        self.progress["config"] = config_parser_global.grapeConfig()
        with io.open(self.progressFile, 'wb') as f:
            p = pickle.Pickler(f)
            p.dump(self.progress)

    @abstractmethod
    def _saveProgress(self, args):
        pass

    def _readProgressFile(self):
        with io.open(self.progressFile, 'rb') as f:
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

    @abstractmethod
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
                    logging.error("No progress file found to continue from. Please enter a command without the "
                                     "--continue option. ")
                    raise e
        newArgs = self.progress["args"]
        #overwrite args with the loaded args
        for key in newArgs.keys():
            args[key] = newArgs[key]
        #load the config
        config_parser_global.resetGrapeConfig(self.progress["config"])
        if deleteProgressFile:
            self._removeProgressFile()
