import io
import logging
import os
from vine import config_parser_global
from vine import config_parser_user
from vine import config_parser_workspace
from vine import utility
from vine import grapeGit as git
from vine.option import Option
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.vine_logging import log_wrapper


class AddSubproject(Option, WorkspaceDirHandler):
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
        projectType = config.get(Option.SECTION_WORKSPACE, "subprojectType").strip().lower()
        if args["--subtree"]:
            projectType = "subtree"
        if args["--submodule"]:
            projectType = "submodule"
        if args["--nested"]:
            projectType = "nested"
        # can happen with invalid type in .grapeconfig and no type specified at command line
        if projectType not in ["subtree", "submodule", "nested"]:
            logging.info("Invalid subprojectType specified in .grapeconfig section [workspace].")
        return projectType

    @log_wrapper
    def execute(self, args):
        name = args["--name"]
        if os.name == 'nt':
            prefix = args["--prefix"].replace(os.path.sep, os.path.altsep)
        else:
            prefix = args["--prefix"]
        url = args["--url"]
        fullurl = git.parseSubprojectRemoteURL(
            url, execution_path=self.workspace_dir)
        branch = args["--branch"]
        config = config_parser_global.grapeConfig()
        projectType = self.parseSubprojectType(config, args)
        proceed = args["--noverify"]
        if projectType == "subtree":
            #  whether or not to squash
            squash = args["--squash"] or config.get(Option.SECTION_SUBTREES, "mergePolicy").strip().lower() == "squash"
            squash = squash and not args["--nosquash"]
            squash_arg = "--squash" if squash else ""
            # expand the URL
            if not proceed:
                use_squash = "using a squash merge." if squash else ""
                proceed = utility.userInput(
                    f"About to create a subtree called {name} at path " +
                    f"{prefix},\ncloned from {fullurl} at " +
                    f"{branch} {use_squash}\nProceed? [y/n]", "y")

            if proceed:
                git.subtree(f"add {squash_arg} --prefix={prefix} {fullurl} {branch}",
                            execution_path=self.workspace_dir)

                #update the configuration file
                current_cfg_names = config.get(Option.SECTION_SUBTREES, "names").split()
                if not current_cfg_names or current_cfg_names[0].lower() == "none":
                    config.set("subtrees", "names", name)
                else:
                    current_cfg_names.append(name)
                    config.set("subtrees", "names", ' '.join(current_cfg_names))

                section = f"subtree-{name}"
                config.add_section(section)
                config.set(section, "prefix", prefix)
                config.set(section, "remote", url)
                config.set(section, "topicPrefixMappings", f"?:{branch}")
                with io.open(os.path.join(self.workspace_dir, ".grapeconfig"), "w") as f:
                    config.write(f)
                logging.info("Successfully added subtree branch. \n" +
                      "Updated .grapeconfig file. Review changes and then commit. ")
        elif projectType == "submodule":
            if not proceed:
                proceed = utility.userInput(
                    f"about to add {name} as a submodule at path {prefix}," +
                    f"\ncloned from {url} at branch {branch}.\nproceed?" +
                    " [y/n]", "y")
            if proceed:
                git.submodule(f"add --name {name} --branch {branch} {url} {prefix}",
                              execution_path=self.workspace_dir)
                logging.info(f"Successfully added submodule {name} at " +
                             f"{prefix}. Please review changes and commit.")
        elif projectType == "nested":
            if not proceed:
                proceed = utility.userInput(
                    f" about to clone {name} as a nested git repo at path" +
                    f" {prefix},\ncloned from {url} at branch" +
                    f" {branch}.\nProceed? [y/n]", 'y')
            if proceed:
                git.clone(source_repo=fullurl, clone_repo=prefix,
                          execution_path=self.workspace_dir)
                ignorePath = os.path.join(
                    git.baseDir(execution_path=self.workspace_dir), ".gitignore")
                with io.open(ignorePath, 'a') as ignore:
                    ignore.writelines([prefix+'\n'])
                git.add(ignorePath, execution_path=self.workspace_dir)
                wsConfig = config_parser_workspace.GrapeConfigParserWorkspace(self.workspace_dir)
                currentSubprojects = wsConfig.getList("nestedProjects", "names")
                currentSubprojects.append(name)
                wsConfig.set("nestedProjects", "names", ' '.join(currentSubprojects))
                newSection = f"nested-{name}"
                wsConfig.ensureSection(newSection)
                wsConfig.set(newSection, "prefix", prefix)
                wsConfig.set(newSection, "url", url)
                configFileName = os.path.join(self.workspace_dir, ".grapeconfig")
                with io.open(configFileName, 'w') as f:
                    wsConfig.write(f)
                git.add(f'{configFileName}', execution_path=self.workspace_dir)
                git.commit(f"{ignorePath} {configFileName} -m " +
                           f"\"GRAPE: Added nested subproject {prefix}\"",
                           execution_path=self.workspace_dir)
                # update the runtime config with the new workspace .grapeconfig's settings.
                config_parser_global.read(workspace_dir=self.workspace_dir)

                userConfig = config_parser_user.GrapeConfigParserUser(workspace_dir=self.workspace_dir)
                userConfig.ensureSection(newSection)
                userConfig.set(newSection, "active", "True")
                config_parser_global.writeConfig(userConfig, os.path.join(self.workspace_dir, ".git", ".grapeuserconfig"))

        return True

    @staticmethod
    def activateNestedSubproject(subprojectName, userconfig, filterArg, workspace_dir):
        config = config_parser_global.grapeConfig()
        prefix = config.get(f"nested-{subprojectName}", "prefix")
        url = config.get(f"nested-{subprojectName}", "url")
        fstr = f"--filter={filterArg}" if filterArg else ""
        fullurl = git.parseSubprojectRemoteURL(url, execution_path=workspace_dir)
        section = f"nested-{subprojectName}"
        userconfig.ensureSection(section)
        currentlyActive = userconfig.getboolean(section, "active")
        if not currentlyActive:
            destDir = os.path.join(workspace_dir, prefix)
            if not (os.path.isdir(destDir) and os.listdir(destDir)):
                git.clone(argstr=f"-n {fstr}", source_repo=fullurl, clone_repo=prefix,
                          execution_path=workspace_dir)
            elif '.git' in os.listdir(destDir):
                pass
            else:
                logging.warning("WARNING: inactive nested subproject " +
                                f"{prefix} has files but is not a git repo")
                return False
        userconfig.set(section, "active", "True")
        config_parser_global.writeConfig(userconfig, os.path.join(workspace_dir, ".git", ".grapeuserconfig"))
        return True

    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_SUBTREES)
        config.ensureSection(self.SECTION_WORKSPACE)
        config.ensureSection(self.SECTION_NESTED_PROJECTS)
        config.set(self.SECTION_SUBTREES, "mergePolicy", "squash")
        config.set(self.SECTION_WORKSPACE, "subprojectType", "subtree")
        config.set(self.SECTION_NESTED_PROJECTS, "names", "")
