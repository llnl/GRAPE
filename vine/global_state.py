from grape.docopt.docopt import docopt
from grape.docopt.docopt import Dict as docoptDict

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
    if isinstance(args, docoptDict):
        if args["-v"]:
            setVerbosity(2)
        elif args["-q"]:
            setVerbosity(0)
        else:
            setVerbosity(1)
        if args["--noProgress"]:
            setShowProgress(False)
        else:
            setShowProgress(True)
    if isinstance(args, list):
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
