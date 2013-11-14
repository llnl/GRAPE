import os, StringIO, subprocess, tempfile

def ensure_dir(f):
    d = os.path.dirname(f)
    print("d:"+d)
    if not os.path.exists(d):
        print("making "+d)
        os.makedirs(d)

def executeSubProcess(command, workingDirectory=tempfile.gettempdir(), outFileHandle=1, verbose=True):
    if verbose:
        print("Executing: " + command + ": Working Directory: " + workingDirectory)
    #***************************************************************************************************************
    #Note: Even though python's documentation says that "shell=True" opens up a computer for malicious shell commands,
    # it is needed to allow users to fully utilize shell commands, such as cd.
    #***************************************************************************************************************
    process = subprocess.Popen(command, stdout=outFileHandle, stderr=outFileHandle, shell=True, cwd=workingDirectory)
    process.wait()
    if process.returncode != 0:
        print("Command '" + command + "': exited with error code " + str(process.returncode))
    return process.returncode

def GetCurrentBranch():
    out = StringIO.StringIO()
    git("rev-parse","--abbrev-ref","HEAD",_out=out)
    toReturn = out.getvalue().strip().encode('ascii')
    out.close()
    return toReturn

def GetSHA(desc):
    out = StringIO.StringIO()
    git("rev-parse",desc,_out=out)
    toReturn = out.getvalue().strip().encode('ascii')
    out.close()
    return toReturn

def GetUserName(defaultName = os.getlogin()):
    return userInput("Enter LC User Name:",defaultName)

def GitDir():
    out = StringIO.StringIO()
    git("rev-parse","--show-toplevel",_out=out)
    toReturn = out.getvalue().strip().encode('ascii')
    out.close()
    return toReturn

# ask the user for something and return what they put in
# NOTE THE SPECIAL TREATEMENT for y/n/Y/N defaults:
# if default is 'y', 'n', 'Y', or 'N', this will evaluate
# to True if the user inputs anything that starts with a 'y' or 'Y',
# and will evaluate to False if the user inputs anything that starts
# with a 'N' or 'n'.
def userInput(message,default):
    print(message)
    if (default is "" or default is None):
        return raw_input('==> ').strip()
    else:
        value = raw_input("(def: %s) ==> " % (default)).strip()
        value = default if value is "" else value
        value = value.lower()[0] if default.lower() is 'y' or default.lower() is 'n' else value
        if (value == 'y'):
            value = True
        if (value == 'n'):
            value = False
        return value

def Cascade(list, op):
    ancestor = list[0]
    for descendent in list[1:]:
        exec op
        ancestor = descendent
   
