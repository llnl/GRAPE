import os
import subprocess
import sys
import tempfile
from grape.vine import global_state
from grape.vine import vine_logging


def executeSubProcess(command, workingDirectory=os.getcwd(), verbose=2,
                      stream=False):
    output = None
    if verbose == -1:
        verbose = global_state.globalVerbosity
    if verbose > 1:
        print(f"Executing: {command}" + "\n\t Working Directory: " +
              f"{workingDirectory}")
    #***************************************************************************************************************
    #Note: Even though python's documentation says that "shell=True" opens up a computer for malicious shell commands,
    # it is needed to allow users to fully utilize shell commands, such as cd.
    #***************************************************************************************************************
    if stream:
        process = subprocess.Popen(command,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT,
                                   shell=(os.name != "nt"),
                                   cwd=workingDirectory)
        _wait_for_process(process, command)
        if verbose > 0:
            sys.stdout.write(str(process.stdout))
            sys.stdout.flush()
    else:
        with tempfile.TemporaryFile() as tmpFile:
            process = subprocess.Popen(command,
                                       stdout=tmpFile.fileno(),
                                       stderr=subprocess.STDOUT,
                                       shell=(os.name != "nt"),
                                       cwd=workingDirectory)
            _wait_for_process(process, command)
            tmpFile.seek(0)
            output = tmpFile.read()
            if verbose > 1:
                print(str(output.strip()))
        # Python 3.x subprocess modules returns bytes in place of strings.
        if isinstance(output, bytes):
            output = output.decode()
        process.output = output

    if process.returncode != 0 and verbose > 1:
        print(f"Command '{command}': exited with error code " +
              f"{process.returncode}")
    return process


def _wait_for_process(process, command):
    while process.poll() is None:
        try:
            process.wait(3)
        except subprocess.TimeoutExpired:
            print(f"COMMAND: '{command}' STILL RUNNING...")
