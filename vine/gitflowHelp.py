import option

# Display a help image for gitflow tasks
class GitflowHelp(option.Option):
    def __init__(self):
        self._key = "help"
        self._section = "Gitflow Tasks"

    def description(self):
        return "Display a gitflow diagram to help make a decision"

    def execute(self):
        diagram = ""+ \
        " choice                time --------->                                            Branch Type       \n"+\
        "____________________________________________________________________________________________________\n"+\
        "\n"+\
        "           [4.20.0] ---- [4.20.1,Release_4_20]                                    Stable Release    \n"+\
        "           /       \     /                                                                          \n"+\
        "rel)      /         []--[]                                                        Release bugfix    \n"+\
        "         /                \                                                                         \n"+\
        "       [4.19.last] --[4.21.1] ------[4.21.2]------[4.21.3] ---- [4.21.4 ]         master            \n"+\
        "          \            \             /            /     \       /                                   \n"+\
        "hot)       \            \           /            /       []---[]                  hotfix  (fix weekly)\n"+\
        "            \            \         /            /              \                                    \n"+\
        "minor)       \            \       /       []--- []              \                 minor Release Branch (fix nightly)\n"+\
        "              \            \     /       /        \              \                                  \n"+\
        "               [] --------- []--[] ---- []------- [] ------- [STABLE]----[TEST]   develop (shared history)\n"+\
        "                 \          |   / \     /                       \           /                       \n"+\
        "                  \          \ /   \   /                         \         /                        \n"+\
        "rev)               []------ [F1]   []-[F2]                       [] ---- [F3]     feature (new development)\n"

        print(diagram)
        # return False as we expect the user will want to do something else after seeing this diagram
        # Returning False gives them a new prompt instead of exiting out.
        return False
