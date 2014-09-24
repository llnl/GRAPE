import os
import ConfigParser
import grapeConfig
import option
import utility
import grapeGit as git
import subtree


class AddSubproject(option.Option):
    """
        grape addSubproject
        Adds a new project to this workspace (such as a new library or a new test suite)

        Usage: grape-addSubproject  --name=<name> --prefix=<prefix> --url=<url> --branch=<branch>
                                    [--subtree [--squash | --nosquash] | --submodule]
                                    [--noverify]
                                    [-v]

        Options:
        --name=<name>       The name of the subproject.
        --prefix=<prefix>   Path to place the subproject in your current workspace. (Relative to the top level
                            directory in your workspace.)
        --url=<url>         The URL (SSH, HTTPS, or Relative URL) of the new project's repository.
        --branch=<branch>   The branch name of the subproject you want to add.
        --subtree           Add this subproject as a subtree. Default behavior if .grapeconfig.workspace.subprojectType
                            is subtree.
        --squash            For subtree projects, if --squash is used, will add <commit> as a squash merge.
                            This defaults to true if .grapeconfig.subtrees.mergePolicy is squash.
        --nosquash          For subtree projects, if --nosquash is used, will ensure full history of <branch> is merged
                            in.
        --submodule         Add this subproject as a submodule. Default behavior if
                            .grapeconfig.workspace.subprojectType is submodule.
        --noverify          Set to prevent grape from asking for user verification before adding the subproject.
        -v                  Set to print all git commands that are issued

    """
    def __init__(self):
        super(AddSubproject, self).__init__()
        self._key = "addSubproject"
        self._section = "Project Management"

    def description(self):
        return "Adds a new subproject (such as a library) as either a subtree or a submodule"

    def execute(self, args):
        name = args["--name"]
        prefix = args["--prefix"]
        url = args["--url"]
        branch = args["--branch"]
        quiet = not args["-v"]
        config = grapeConfig.grapeConfig()
        usesubtree = config.get("workspace", "subprojectType").strip().lower() == "subtree"
        usesubtree = usesubtree and not args["--submodule"]
        usesubmodule = not usesubtree
        proceed = args["--noverify"]
        if usesubtree:
            #  whether or not to squash
            squash = args["--squash"] or config.get("subtrees", "mergePolicy").strip().lower() == "squash"
            squash = squash and not args["--nosquash"]
            squash_arg = "--squash" if squash else ""
            # expand the URL
            fullurl = subtree.parseSubtreeRemote(url)
            if not proceed:
                proceed = utility.userInput("About to create a subtree called %s at path %s,\n"
                                            "cloned from %s at %s " % (name, prefix, fullurl, branch) +
                                            ("using a squash merge." if squash else "") + "\nProceed? [y/n]", "y")

            if proceed:
                os.chdir(utility.workspaceDir())
                git.subtree("add %s --prefix=%s %s %s" % (squash_arg, prefix, fullurl, branch), quiet=quiet)

                #update the configuration file
                current_cfg_names = config.get("subtrees", "names").split()
                if not current_cfg_names or current_cfg_names[0].lower() == "none":
                    config.set("subtrees", "names", name)
                else:
                    current_cfg_names.append(name)
                    config.set("subtrees", "names", ' '.join(current_cfg_names))

                section = "subtree-%s" % name
                config.add_section(section)
                config.set(section, "prefix", prefix)
                config.set(section, "remote", url)
                config.set(section, "topicPrefixMappings", "?:%s" % branch)
                with open(os.path.join(utility.workspaceDir(), ".grapeconfig"), "w") as f:
                    config.write(f)
                print("Successfully added subtree branch. \n"
                      "Updated .grapeconfig file. Review changes and then commit. ")
        elif usesubmodule:
            if not proceed:
                proceed = utility.userInput("about to add %s as a submodule at path %s,\n"
                                            "cloned from %s at branch %s.\nproceed? [y/n]" %
                                            (name, prefix, url, branch), "y")
            if proceed:
                git.submodule("add --name %s --branch %s %s %s" % (name, branch, url, prefix), quiet=quiet)
                print("Successfully added submodule %s at %s. Please review changes and commit." % (name, prefix))
        return True

    def setDefaultConfig(self, config):
        config.ensureSection("subtrees")
        config.ensureSection("workspace")

        config.set("subtrees", "mergePolicy", "squash")
        config.set("workspace", "subprojectType", "subtree")