import os
import ConfigParser
import grapeConfig
import option
import utility
import grapeGit as git


class AddSubproject(option.Option):
    """
        grape addSubproject
        Adds a new project to this workspace (such as a new library or a new test suite)

        Usage: grape-addSubproject  --name=<name> --prefix=<prefix> --url=<url> --branch=<branch>
                                    [--subtree [--squash | --nosquash] | --submodule | --nested]
                                    [--noverify]


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
        --nested            Add this subproject as a nested git project. While in the main repository, git will ignore
                            all activity in this subproject. GRAPE commands such as checkout, status, and commit will
                            act across all nested subprojects in much the same way as grape manages submodules.
        --noverify          Set to prevent grape from asking for user verification before adding the subproject.


    """
    def __init__(self):
        super(AddSubproject, self).__init__()
        self._key = "addSubproject"
        self._section = "Project Management"

    def description(self):
        return "Adds a new subproject (such as a library) as a subtree, submodule, or nested subproject. "

    @staticmethod
    def parseSubprojectType(config, args):
        projectType = config.get("workspace", "subprojectType").strip().lower()
        if args["--subtree"]:
            projectType = "subtree"
        if args["--submodule"]:
            projectType = "submodule"
        if args["--nested"]:
            projectType = "nested"
        # can happen with invalid type in .grapeconfig and no type specified at command line
        if projectType != "subtree" and projectType != "submodule" and projectType != "nested":
            utility.printMsg("Invalid subprojectType specified in .grapeconfig section [workspace].")
        return projectType

    def execute(self, args):
        name = args["--name"]
        prefix = args["--prefix"]
        url = args["--url"]
        fullurl = utility.parseSubprojectRemoteURL(url)
        branch = args["--branch"]
        config = grapeConfig.grapeConfig()
        projectType = self.parseSubprojectType(config, args)
        proceed = args["--noverify"]
        if projectType == "subtree":
            #  whether or not to squash
            squash = args["--squash"] or config.get("subtrees", "mergePolicy").strip().lower() == "squash"
            squash = squash and not args["--nosquash"]
            squash_arg = "--squash" if squash else ""
            # expand the URL
            if not proceed:
                proceed = utility.userInput("About to create a subtree called %s at path %s,\n"
                                            "cloned from %s at %s " % (name, prefix, fullurl, branch) +
                                            ("using a squash merge." if squash else "") + "\nProceed? [y/n]", "y")

            if proceed:
                os.chdir(utility.workspaceDir())
                git.subtree("add %s --prefix=%s %s %s" % (squash_arg, prefix, fullurl, branch))

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
                utility.printMsg("Successfully added subtree branch. \n"
                      "Updated .grapeconfig file. Review changes and then commit. ")
        elif projectType == "submodule":
            if not proceed:
                proceed = utility.userInput("about to add %s as a submodule at path %s,\n"
                                            "cloned from %s at branch %s.\nproceed? [y/n]" %
                                            (name, prefix, url, branch), "y")
            if proceed:
                git.submodule("add --name %s --branch %s %s %s" % (name, branch, url, prefix))
                print("Successfully added submodule %s at %s. Please review changes and commit." % (name, prefix))
        elif projectType == "nested":
            if not proceed:
                proceed = utility.userInput(" about to clone %s as a nested git repo at path %s,\n"
                                            "cloned from %s at branch %s.\nProceed? [y/n]" %
                                            (name, prefix, url, branch), 'y')
            if proceed:
                git.clone("%s %s" % (fullurl, prefix))
                ignorePath = os.path.join(git.baseDir(), ".gitignore")
                with open(ignorePath, 'a') as ignore:
                    ignore.writelines([prefix+'\n'])
                git.add(ignorePath)
                wsConfig = grapeConfig.workspaceConfig()
                currentSubprojects = wsConfig.getList("nestedProjects", "names")
                currentSubprojects.append(name)
                wsConfig.set("nestedProjects", "names", ' '.join(currentSubprojects))
                newSection = "nested-%s" % name
                wsConfig.ensureSection(newSection)
                wsConfig.set(newSection, "prefix", prefix)
                wsConfig.set(newSection, "url", url)
                configFileName = os.path.join(utility.workspaceDir(), ".grapeconfig")
                with open(os.path.join(configFileName), 'w') as f:
                    wsConfig.write(f)
                git.add(configFileName)
                git.commit("%s %s -m \"GRAPE: Added nested subproject %s\"" % (ignorePath, configFileName, prefix))
                # update the runtime config with the new workspace .grapeconfig's settings.
                grapeConfig.read()

                userConfig = grapeConfig.grapeUserConfig()
                userConfig.ensureSection(newSection)
                userConfig.set(newSection, "active", "True")
                grapeConfig.writeConfig(userConfig, os.path.join(utility.workspaceDir(), ".git", ".grapeuserconfig"))

        return True

    @staticmethod
    def activateNestedSubproject(subprojectName, userconfig):
        wsDir = utility.workspaceDir()
        config = grapeConfig.grapeConfig()
        prefix = config.get("nested-%s" % subprojectName, "prefix")
        url = config.get("nested-%s" % subprojectName, "url")
        fullurl = utility.parseSubprojectRemoteURL(url)
        section = "nested-%s" % subprojectName
        userconfig.ensureSection(section)
        currentlyActive = userconfig.getboolean(section, "active")
        if not currentlyActive:
            destDir = os.path.join(wsDir, prefix)
            if not (os.path.isdir(destDir) and os.listdir(destDir)):
                git.clone("%s %s" % (fullurl, prefix))
            elif '.git' in os.listdir(destDir):
                pass
            else:
                utility.printMsg("WARNING: inactive nested subproject %s has files but is not a git repo" % prefix)
                return False
        userconfig.set(section, "active", "True")
        grapeConfig.writeConfig(userconfig, os.path.join(wsDir, ".git", ".grapeuserconfig"))
        return True

    def setDefaultConfig(self, config):
        config.ensureSection("subtrees")
        config.ensureSection("workspace")
        config.ensureSection("nestedProjects")
        config.set("subtrees", "mergePolicy", "squash")
        config.set("workspace", "subprojectType", "subtree")
        config.set("nestedProjects", "names", "")
