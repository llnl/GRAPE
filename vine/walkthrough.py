import sys
import option
if not ".." in sys.path:
    sys.path.append( ".." )
import git

class Walkthrough(option.Option):
    key = 'w'
    section = " CODE REVIEWS "

    def Description(self):
        return "Walk through diffs between branches"

    def Execute(self):
        b1 = utility.userInput("Enter name of first branch to compare","HEAD")
        b2 = utility.userInput("Enter name of second branch to compare", "develop")
        print("Running git diff %s %s..., use Ctrl-C to stop diff" %(b1,b2))

        # may want to exit out of diffs early, need to make sure to pass the
        # signal down
        try:
            p = git.diff(b1,b2,_bg=True)
            p.wait()
        except KeyboardInterrupt:
            p.kill()
        return True

