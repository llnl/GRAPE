import option, utility

# Create a custom sparse checkout view in a new working tree
class NewWorkingTree(option.Option):
    def __init__(self):
        self._key = "cv"
        self._section = "Miscellaneous"

    def description(self):
        return "Create a custom sparse checkout view in a new working tree"

    def execute(self):

        clonePath = ""
        try:
            clonePath = utility.gitDir()
            if clonePath == "":
                return False
        except:
            pass

        clonePath = utility.userInput("Enter path to original clone",clonePath)

        newTree = utility.userInput("Enter name of new working tree")

        newTreePath = utility.userInput("Enter desired location of new working tree (must exist)",
                                os.path.abspath(os.path.join(clonePath,"../")))

        newRepo = os.path.join(newTreePath,newTree)
        #TODO: When grape is installed to PUBLIC, the first argument here should be the
        # publically available git-new-workdir, instead of the version in the local repo.
        p = subprocess.Popen(os.path.join(clonePath,"scripts","git","git-new-workdir")
                             + " "+clonePath+" "+newRepo,shell = True)
        p.wait()

        os.chdir(newRepo)

        return options['uv'].execute()
