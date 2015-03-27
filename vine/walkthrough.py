import sys,os,tempfile
import option
import grapeGit as git
import utility

class Walkthrough(option.Option):
    """ 
    grape w(alkthrough)
    Usage: grape-w [--nogui] [<b1> [<b2>] ] [--] [ <filetree-ish> ]

    Options:
        --nogui         Don't use kompare to do the walkthrough, use whatever diff is your default diff. 

    Optional Arguments:
        <b1>            The first tree to compare
        <b2>            The second tree to compare
        <filetree-ish>  The files to compare.  

    """
    def __init__(self):
        super(Walkthrough, self).__init__()
        self._key = "w"
        self._section = "Code Reviews"

    def description(self):
        return "Walk through diffs between branches"

    def execute(self,args):
        b1 =  args["<b1>"] 
        if not b1: 
            b1 = utility.userInput("Enter name of branch to compare","HEAD")
        b2 = args["<b2>"] if args["<b2>"] else ""
               
        nogui = args["--nogui"] or os.name == "nt"
        # may want to exit out of diffs early, need to make sure to pass the
        # signal down
        files = args["<filetree-ish>"]
        if (not files): 
            files = ""

        # make sure our remote references are up to date if we're comparing with something in the origin repo
        if 'origin' in b1 or 'origin' in b2: 
            try: 
                git.fetch()
            except:
                pass

        if nogui:
            # use default git diff behavior to look at diffs
            p = git.diff("%s %s -- %s" % (b1,b2,files) )
        else:
            # use kompare to browse the diffs.
            p = git.diff("--no-ext-diff -U2000 %s %s -- %s" % (b1,b2,files))
            fname = os.path.join(tempfile.gettempdir(),"gitdifftmp")
            with open(fname,'w') as f:
                f.write(p)
            with open(fname,'r') as f: 
                p2 = utility.executeSubProcess("kompare -",stdin = f)
    
        return True

    def setDefaultConfig(self, config):
        pass

