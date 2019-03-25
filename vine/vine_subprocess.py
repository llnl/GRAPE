import os
import subprocess
import sys
import tempfile
import global_state


def executeSubProcess(command, workingDirectory=os.getcwd(), verbose=2,
                      stdin=sys.stdin, stream = False):

    if verbose == -1:
        verbose = global_state.globalVerbosity
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
    elif global_state.globalShowProgress and os.name == "posix":
        with tempfile.NamedTemporaryFile() as tmpFile:
            launcher = global_state.FollowableCommand(command, workingDirectory, tmpFile, stdin)
            launcher.run(startStreaming=3.0)
            tmpFile.seek( 0 )
            output = tmpFile.read()
            if verbose > 1 and launcher.stopFollowing == 0:
                print(output.strip())
            process = launcher.finishedProcesses.get()
    else:
        with tempfile.TemporaryFile() as tmpFile:
            process = subprocess.Popen(command, cwd=workingDirectory,
                                       shell=(os.name != "nt"),
                                       stdout=tmpFile.fileno(),
                                       stderr=subprocess.STDOUT)
            process.wait()
            tmpFile.seek( 0 )
            output = tmpFile.read()
            if verbose > 1:
                print(output.strip())

    process.output = output
    if process.returncode != 0 and verbose > 1:
        print("Command '" + command + "': exited with error code " + str(process.returncode))
    return process
