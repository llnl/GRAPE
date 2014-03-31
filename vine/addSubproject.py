import os
from vine import grapeConfig
from vine.option import Option
from vine import utility
from vine import grapeGit as git
from vine import subtree

class AddSubproject(Option):
    """
        grape addSubproject
        Adds a new project to this workspace (such as a new library or a new test suite)

                Usage: grape-addSubproject  --name=<name> --prefix=<prefix> --url=<url> --commit=<commit>
                                            [--subtree [--squash] | --submodule]
                                            [--noverify]
                                            [-v]
        Options:
        --name=<name>       The name of the subproject.
        --prefix=<prefix>   Path to place the subproject in your current workspace. (Relative to the top level
                            directory in your workspace.)
        --url=<url>         The URL (SSH, HTTPS, or Relative URL) of the new project's repository.
        --commit=<commit>   The branch name, tag, or SHA of the commit you want to add.
        --subtree           Add this subproject as a subtree. Default behavior if .grapeconfig.workspace.subprojectType
                            is subtree.
        --squash            For subtrees projects, if --squash is used, will add <commit> as a squash merge.
                            This defaults to true if .grapeconfig.subtrees.mergePolicy is squash.
        --submodule         Add this subproject as a submodule. Default behavior if .grapeconfig.workspace.subprojectType
                            is submodule.
        --noverify          Set to prevent grape from asking for user verification before adding the subproject.
        -v                  Set to print all git commands that are issued.
    """
    def __init__(self):
        super(Option, self).__init__()
        self._key = "addSubproject"
        self._section = "Workspace"

    def execute(self, args):
        name = args["--name"]
        prefix = args["--prefix"]
        url = args["--url"]
        commit = args["--commit"]
        quiet = not args["-v"]
        config = grapeConfig.grapeConfig()
        usesubtree = config.get("workspace", "subprojectType").strip().lower() == "subtree"
        usesubtree = usesubtree and not args["--submodule"]
        usesubmodule = not usesubtree
        verify = not args["--noverify"]
        if usesubtree:
            #  whether or not to squash
            squash = args["--squash"] or config.get("subtrees", "mergePolicy").strip().lower() == "squash"
            squash_arg = "--squash" if squash else ""
            # expand the URL
            fullurl = subtree.parseSubtreeRemote(url)
            proceed = not verify
            if verify:
                proceed = utility.userInput("About to create a subtree at called %s at path %s,\n"
                                            "cloned from %s at %s\n " +
                                            ("using a squash merge." if squash else "") + "\nProceed? [y/n]", "y")

            if proceed:
                git.subtree("add %s --prefix=%s %s %s" % (squash_arg, prefix, fullurl, commit), quiet=quiet)
                #update the configuration file
                config.add_section(name)
                config.set(name, "prefix", prefix)
                config.set(name, "remote", url)
                config.set(name, "topicPrefixMappings", "?:master")
                with open(os.path.join(utility.workspaceDir(), ".grapeconfig"), "-w") as f:
                    config.write(f)
                print("Successfully added subtree commit. \n"
                      "Updated .grapeconfig file. Review changes and then commit. ")
        elif usesubmodule:
            proceed = not verify
            if verify:
                proceed = utility.userInput("about to add %s as a submodule at path %s,\n"
                                            "cloned from %s at %s.\nproceed? [y/n]", "y")
            if proceed:
                git.submodule("add --name %s --branch %s %s %s" % (name, commit, url, prefix), quiet=quiet)
                print("Successfully added submodule %s at %s. Please review changes and commit." % (name, prefix))







        return True