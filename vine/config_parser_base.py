import ConfigParser
import os
import cStringIO


class GrapeConfigParserBase(ConfigParser.ConfigParser, object):

    GIT_DIR = '.git'
    GRAPE_CONFIG = '.grapeconfig'

    def __init__(self, workspaceDir=None, configString=None):
        ConfigParser.ConfigParser.__init__(self)

        if workspaceDir:
            self.read(os.path.join(workspaceDir, self.GRAPE_CONFIG))
        if configString:
            self.readfp(cStringIO.StringIO(configString))

    def ensureSection(self, section):
        try:
            self.add_section(section)
            if "nested-" in section:
                self.set(section,"active", "False")
        except ConfigParser.DuplicateSectionError:
            pass

    def getAllNestedSubprojects(self):
        list_ = []
        try:
            list_ = self.getList("nestedProjects", "names")
        except:
            pass
        finally:
            return list_

    def getList(self, section, cfgOption, raw=False, cfgVars=None):
        return self.get(section, cfgOption, raw=raw, vars=cfgVars).split()

    def branchPrefix(self, branchName):
        return branchName.split('/')[0]

    def getPublicBranchFor(self, branch, getDestinationBranch=True):
        if getDestinationBranch:
            destinationBranches = self.getMapping("flow", "topicDestinationMappings")
            try:
                destinationBranch = destinationBranches[self.branchPrefix(branch)]
                return destinationBranch
            except KeyError:
                pass

        publicBranches = self.getPublicBranchList()
        if branch in publicBranches:
            return branch
        publicMapping = self.getMapping("flow", "topicPrefixMappings")
        return publicMapping[self.branchPrefix(branch)]

    def getMapping(self, section, cfgOption, raw=False, cfgVars=None):
        return self.parseConfigPairList(self.get(section, cfgOption, raw=raw, vars=cfgVars))

    def getPublicBranchList(self):
        return self.get("flow", "publicbranches").split()

    @staticmethod
    def parseConfigPairList(toParse):
        pairs = toParse.split() if toParse else ["none"]
        pairDict = ConfigPairDict()
        if pairs[0].strip().lower() != "none":
            for pair in pairs:
                plist = pair.split(':')
                pairDict[plist[0]] = plist[1]
        return ConfigPairDict(pairDict)


class ConfigPairDict(dict):

    def __getitem__(self, key):
        try:
            return super(ConfigPairDict, self).__getitem__(key)
        except KeyError as e:
            if '?' in self.keys():
                return self['?'].replace('?', key)
            else:
                e.message = "GRAPE CONFIG ERROR: No value found for %s, no default '?':<value> in config." % key
                raise e
