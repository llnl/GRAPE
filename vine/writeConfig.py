import config_parser_global
import option


class WriteConfig(option.Option):
    """
        grape writeConfig: Writes the current configuration to a file, using any configuration set
        by ~/.grapeconfig or your <REPO_BASE>/.grapeconfig.

        Usage:
        grape-writeConfig <file> [--gitflow]

    """
    def __init__(self):
        self._section = "Getting Started"
        self._key = "writeConfig"
        self._config = None

    def description(self):
        return "write a .grapeconfig file based on your current environment"

    def execute(self, args):
        config = config_parser_global.grapeConfig()

        self.setFlowModelConfig(config, args)
        with open(args["<file>"], 'w') as f:
            config.write(f)

    @staticmethod
    def setFlowModelConfig(config, args):
        config.ensureSection("flow")
        config.ensureSection("versioning")
        config.ensureSection("patch")
        if args["--gitflow"]:
            # [flow]
            config.set("flow", "publicBranches", "master develop")
            config.set("flow", "topicPrefixMappings",
                       "hotfix:master bugfix:develop feature:develop ?:develop release:develop")
            config.set("flow", "topicDestinationMappings", "release:master")
            config.set("flow", "publishpolicy", "?:merge master:cascade->develop")
            # [versioning]
            config.set("versioning", "updateTag", "True")
            config.set("versioning", "branchslotmappings", "?:3 master:2")
            # [patch]
            config.set("patch", "branches", "develop master")

    def setDefaultConfig(self, config):
        pass
