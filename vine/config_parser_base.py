from configparser import ConfigParser, DuplicateSectionError
import io
import os
from vine.option import Option


class GrapeConfigParserBase(ConfigParser):

    GIT_DIR = '.git'
    GRAPE_CONFIG = '.grapeconfig'

    def __init__(self, workspaceDir=None, configString=None):
        ConfigParser.__init__(self)

        if workspaceDir:
            ConfigParser.read(self,os.path.join(workspaceDir, self.GRAPE_CONFIG))
        if configString:
            ConfigParser.read_file(self,io.StringIO(configString))


    def read(self, *args,**kwargs):
        ConfigParser.read(self,*args,**kwargs)
        # ensure backwards compatibility with stashURL
        stashURL = None
        try:
            stashURL = self.get("project","stashURL")
        except:
            pass 
            
        if stashURL:
            self.set("project","codeReviewsURL",stashURL)

    def ensureSection(self, section):
        try:
            self.add_section(section)
            if "nested-" in section:
                self.set(section,"active", "False")
            elif "spack" in section:
                self.set(section,"active", "False")
        except DuplicateSectionError:
            pass

    def getAllNestedSubprojects(self):
        list_ = []
        try:
            list_ = self.getList(Option.SECTION_NESTED_PROJECTS, "names")
        except:
            pass
        finally:
            return list_

    def getAllSpackProjects(self):
        list_ = []
        try:
            list_ = self.getList(Option.SECTION_SPACK_PROJECTS, "submodules")
        except:
            pass
        finally:
            return list_

    def getList(self, section, cfgOption, raw=False, cfgVars=None):
        return self.get(section, cfgOption, raw=raw, vars=cfgVars).split()

    def branch_prefix(self, branchName):
        return branchName.split('/')[0]

    def getPublicBranchFor(self, branch, getDestinationBranch=True):
        if getDestinationBranch:
            destinationBranches = self.getMapping(Option.SECTION_FLOW, "topicDestinationMappings")
            try:
                destinationBranch = destinationBranches[self.branch_prefix(branch)]
                return destinationBranch
            except KeyError:
                pass

        publicBranches = self.getPublicBranchList()
        if branch in publicBranches:
            return branch
        publicMapping = self.getMapping(Option.SECTION_FLOW, "topicPrefixMappings")
        return publicMapping[self.branch_prefix(branch)]

    def getMapping(self, section, cfgOption, raw=False, cfgVars=None):
        return self.parseConfigPairList(self.get(section, cfgOption, raw=raw, vars=cfgVars))

    def getPublicBranchList(self):
        return self.get(Option.SECTION_FLOW, "publicbranches").split()

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
            e.message = f"GRAPE CONFIG ERROR: No value found for {key}," +\
                        " no default '?':<value> in config."
            raise e
