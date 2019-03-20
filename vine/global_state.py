import os
import subprocess
import sys
import tempfile
import types
toplevel = os.path.join(os.path.realpath(os.path.dirname(__file__)), os.path.pardir)
if toplevel not in sys.path:
    sys.path.insert(0, toplevel)
from docopt.docopt import docopt
from docopt.docopt import Dict as docoptDict

import multiprocessing
import tailer

global_args = []

globalVerbosity = 1
globalShowProgress = True


CLI =  """
*** GRAPE - Git Replacement for "Awesome" PARSEC Environment **********
Calling grape by itself will pull up the grape menu.
Usage: grape [-v | -q] [--version] [--noProgress] [--np=<numProcs>][<command> <args>...]

Options:
-v           Run in verbose mode. This will print out git output as git commands complete.
-q           Quiet mode. Quiet's all output except for user input prompts.
--noProgress Do not show progress for long-running git subprocesses. This will remove
             a fair amount of process-launch overhead in GRAPE, which can have a speedup of
             about a third.
--np=<int>   The number of processes grape should launch when doing parallel operations.



"""


def setVerbosity(level):
    global globalVerbosity
    globalVerbosity = level

def setShowProgress(val):
    global globalShowProgress
    globalShowProgress = val

def __apply__(args, CLI):
    if type(args) is docoptDict:
        if args["-v"]:
            setVerbosity(2)
        elif args["-q"]:
            setVerbosity(0)
        else:
            setVerbosity(1)
        if args["--noProgress"]:
            setShowProgress(False)
        if args["--np"]:
            import multi_repo_cmd_launcher
            multi_repo_cmd_launcher.MultiRepoCommandLauncher.numProcs = int(args["--np"])
        else:
            setShowProgress(True)
    if type(args) is types.ListType:
        # assume the list has yet to be parsed by docopt into the dict __apply__ expects.
        return __apply__(docopt(CLI,args, options_first=True), CLI)

def applyGlobalArgs(args, CLI=CLI):
    global global_args
    __apply__(args, CLI)
    global_args.append(args)

def popGlobalArgs():
    global global_args
    if len(global_args) > 1:
        global_args.pop()
    __apply__(global_args[-1], CLI)


# thanks to jcollado at stackoverflow for inspiration:
# http://stackoverflow.com/questions/1191374/subprocess-with-timeout
def runFollowableTarget(followableCmd):
    followableCmd.runTarget()

def followFollowableTarget(followableCmd):
    followableCmd.followTarget()

class FollowableProcess(object):
    def __init__(self, process):
        self.output = ''
        self.returncode = process.returncode
        self.pid = process.pid

class FollowableCommand(object):
    def __init__(self, cmd, wd, outfile, stdin):
        self.cmd = cmd
        self.process = None
        self.wd = wd
        self.outfileName = outfile.name
        self.fileno = outfile.fileno()
        self.stdin = stdin
        self.finishedProcesses = multiprocessing.Queue()
        self.stopFollowing = 0

    def runTarget(self):
        # runs a subprocess and produces a finished subprocess in the finishedProcesses Queue.

        process = subprocess.Popen(self.cmd, stdout=self.fileno, stderr=subprocess.STDOUT, shell=(os.name != "nt"),
                               cwd=self.wd, stdin=sys.stdin, bufsize=1)
        process.wait()
        self.finishedProcesses.put(FollowableProcess(process), block=False)

    def followTarget(self):
        # uses tailer to follow the output of the running process
        if os.name == "nt":
            flags = os.O_RDWR | os.O_TEMPORARY
        else:
            flags = os.O_RDWR

        try:
            f = os.open(self.outfileName, flags)
            fo = os.fdopen(f,'r');
            generator = tailer.follow(fo)
            for l in generator:
                print l
        finally:
            os.close(fo)
            os.close(f)

    def run(self, startStreaming=5):

        # the cmd launch process
        thread = multiprocessing.Process(target=runFollowableTarget,args=[self])
        # the tailer.follow process
        followThread = multiprocessing.Process(target=followFollowableTarget, args=[self])
        thread.start()

        thread.join(startStreaming)
        if thread.is_alive():
            # follow output in the outfile
            print "Executing %s\n\tWorking Directory: %s..." % (self.cmd, self.wd)
            followThread.start()
            # keep going until the subprocess is done
            thread.join()
            followThread.terminate()
            self.stopFollowing = 1


def executeSubProcess(command, workingDirectory=os.getcwd(), verbose=2,
                      stdin=sys.stdin, stream = False):

    if verbose == -1:
        verbose = globalVerbosity
    if verbose > 1:
        print("Executing: " + command + "\n\t Working Directory: " + workingDirectory)
    #***************************************************************************************************************
    #Note: Even though python's documentation says that "shell=True" opens up a computer for malicious shell commands,
    # it is needed to allow users to fully utilize shell commands, such as cd.
    #***************************************************************************************************************
    if stream:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=(os.name != "nt"),
                                   cwd=workingDirectory, stdin=stdin, bufsize=1)
        output = ''
        while process.poll() is None:
            out = process.stdout.read(1)
            if verbose > 0:
                sys.stdout.write(out)
                sys.stdout.flush()
            output += out
        process.wait() # should be a noop
        out +=  process.communicate()[0] # also should be a noop
        if verbose > 0:
            sys.stdout.write(out)
            sys.stdout.flush()
        output += out

    # TODO: Followable commands aren't working in Windows right now - initially there were some pickling difficulties,
    # but now we are seeing behaviors that look like multiprocessing subprocesses are being launched in incorrect directories.
    # To be troubleshooted later.
    elif globalShowProgress and os.name == "posix":
        with tempfile.NamedTemporaryFile() as tmpFile:
            launcher = FollowableCommand(command, workingDirectory, tmpFile, stdin)
            launcher.run(startStreaming=3.0)
            tmpFile.seek( 0 )
            output = tmpFile.read()
            if verbose > 1 and launcher.stopFollowing == 0:
                print(output.strip())
            process = launcher.finishedProcesses.get()
    else:
        with tempfile.TemporaryFile() as tmpFile:
            process = subprocess.Popen( command, cwd=workingDirectory, shell=(os.name != "nt"), stdout=tmpFile.fileno(),
                                        stderr=subprocess.STDOUT )
            process.wait()
            tmpFile.seek( 0 )
            output = tmpFile.read()
            if verbose > 1:
                print(output.strip())

    process.output = output
    if process.returncode != 0 and verbose > 1:
        print("Command '" + command + "': exited with error code " + str(process.returncode))
    return process


def printMsg(msg):
    global globalVerbosity
    if globalVerbosity > 0:
        print("GRAPE: %s" % msg)
