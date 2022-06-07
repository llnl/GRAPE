from abc import ABC, abstractmethod
import io
import logging
import os
import pickle
from vine import config_parser_global
from vine import grape_errors
from vine import grapeGit as git


class Resumable(ABC):

    def __init__(self):
        super(Resumable, self).__init__()
        self._key = ""
        self.progress = {}
        self.progressFile = None

    def set_progress_file(self, *, execution_path):
        try:
            gitDir = str(git.gitDir(execution_path=execution_path))
            progressFile = os.path.join(gitDir, f"grapeProgress{self._key}")
            self._reset_progress(progressFile)
        except grape_errors.GrapeGitError:
            # can happen if called from outside a workspace, create a .grapeProgress file
            # in the user's $HOME directory
            progressFile = os.path.join(os.path.expanduser('~'), f".grapeProgress{self._key}")
            self._reset_progress(progressFile)

    def _reset_progress(self, progress_file_path):
        if not self.progressFile or self.progressFile != progress_file_path:
            self.progressFile = progress_file_path
            self.progress = {}

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
    def _resume(self, args, deleteProgressFile=True, *, workspace_dir):
        if not self.progressFile:
            self.set_progress_file(execution_path=workspace_dir)
        try:
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
