import option

import os
import re
import StringIO
import ConfigParser

import grapeGit as git
import grapeConfig
import utility

class Version(option.Option):
    """
    grape version
    This command is used for projects that wish to have their version numbers managed by grape.
    The read subcommand is a no-op - it is used internally by other grape/vine modules. 

    Usage: grape-version init <version> --file=<path> [--matchTo=<str>] [--prefix=<verPrefix>] [-suffix=<verSuffix>]
                                                      [--tag | --notag | --updateTag=<bool>]
           grape-version tick [--major | --minor | --slot=<int>]
                              [--tag | --notag | --updateTag=<bool>]
                              [--matchTo=<matchTo>]
                              [--prefix=<prefix>] [--suffix=<sufix>] [--tagPrefix=<prefix>] [--tagSuffix=<sufix>][--file=<path>]
                              [--nocommit]
                              [--notick]
                              [--tagNested]
                              [--public=<branch>]
           grape-version read [--prefix=<prefix>] [--suffix=<suffix>] [--file=<file>]

    Arguments:
        <version>           Used by grape version init, this is the initial version that grape will start counting from.

    Options:
        --file=<file>       The file to store the version number. When used with init, this is mandatory, and
                            grape will update your .grapeconfig file for future version number lookups.
                            [default: .grapeconfig.versioning.file]
        --matchTo=<matchTo> The regex to match to before reaching the version descriptor. Grape will look for the string
                            literals '<prefix>' and '<suffix>' in your regex and substitute your values for <prefix>
                            and <suffix> in their place. Default can be overridden using
                            .grapeconfig.versioning.branchVersionRegexMappings.
                            Note that, if defining matchTo in .grapeconfig.versioning.branchVersionRegexMappings, you
                            should ensure you use \s instead of ' ' as part of your regex, as the list of mappings uses
                            whitespace as a delimiter.
                            Currently, grape expects there to be 4 groups in your regex, with the version number in
                            group 3.
                            [default: (VERSION_ID\s*=\s*)(<prefix>)(\S+)(<suffix>)]
        --matchGroup=<int>  The regex group to pick the version number from. [default:3]
        --prefix=<prefix>   The version number prefix for version string to match in <file>, such as the 'v' in v1.2.3.
                            [default: .grapeconfig.versioning.prefix]
        --suffix=<suffix>   The version number suffix for grape-version to match in <file>, such as the 'm' in v1.2.3.m
                            [default: ]
        --major             Tick the Major (1st) version number.
        --minor             Tick the Minor (2nd) version number.
        --slot=<int>        Tick the <int>'th version number. 1 = Major, 2 = Minor, 3 = third, etc. If <int> is bigger
                            than the current max number of digits, the version number will be extended to have <int>
                            digits. Default value comes from .grapeconfig.versioning.branchSlotMappings. 
        --public=<branch>   The public branch to use for determine the slot to tick. Default based on 
                            .grapeconfig.flow.topicprefixmappings. Grape publish uses this option to ensure the version
                            ticking is consistent with the --public option passed to grape publish. 
        --updateTag=<bool>  If true, update the version git annotated tag. [default: .grapeconfig.versioning.updateTag]
        --tag               Forces updateTag to be True.
        --notag             Forces updateTag to be False.
        --tagPrefix=<str>   The prefix for the git version tags. [default: v]
        --tagSuffix=<str>   The suffix for the git version tags. Default value comes from
                            .grapeconfig.versioning.branchTagSuffixMappings.
        --nocommit          Do not create a new commit, just modify <file>. This implies --updateTag=False.
        --notick            Do not tick the version in <file>. Useful with --tag to tag HEAD as being the current
                            version in <file>.
        --tagNested         Tag any active nested subprojects. 
        


    """
    def __init__(self):
        super(Version, self).__init__()
        self._key = "version"
        self._section = "Gitflow Tasks"
        self.matchedLine = None
        self.r = None

    def description(self):
        return "Update the version for your current project."

    def parseArgs(self, args): 
        config = grapeConfig.grapeConfig()
        # parse tagSuffix for version mappings
        if args["--tagSuffix"] is None: 
            branch2suffix = config.getMapping("versioning", "branchtagsuffixmappings")
            args["--tagSuffix"] = branch2suffix[git.currentBranch()]

    def execute(self, args):
        self.parseArgs(args)
        if args["init"]:
            self.initializeVersioning(args)
        if args["tick"]:
            self.tickVersion(args)
        if args["read"]:
            config = grapeConfig.grapeConfig()
            fileName = config.get("versioning","file")
            try:
                with open(fileName) as f:
                    slots = self.readVersion(f, args)
                    self.ver = self.slotsToString(args, slots)
            except IOError:
                self.ver = ""
        return True

    def initializeVersioning(self, args):
        config = grapeConfig.grapeConfig()
        version = StringIO.StringIO()
        version.write("VERSION_ID = %s" % args["<version>"])
        version.seek(0)
        version = self.readVersion(version, args)
        if args["--file"]:
            fname = args["--file"]
            with open(fname, 'w+') as f:
                version = self.writeVersion(f, version, args)
            self.stageVersionFile(fname)
            config.set("versioning", "file", fname)
            configFile = os.path.join(git.baseDir(), ".grapeconfig")
            grapeConfig.writeConfig(config, configFile)
            self.stageGrapeconfigFile(configFile)
            if not args["--nocommit"]:
                git.commit("%s %s -m \"GRAPE: added initial version info file %s\"" % (fname, configFile, fname))
                self.tagVersion(version, args)

    def tickVersion(self, args):
        config = grapeConfig.grapeConfig()
        fileName = config.get("versioning", "file")
        with open(fileName) as f:
            slots = self.readVersion(f, args)
            self.ver = self.slotsToString(args, slots)
            
        if not args["--notick"]:
            slot = args["--slot"]
            if not slot:
                slotMappings = config.getMapping("versioning", "branchSlotMappings")
                if args["--public"]:
                    publicBranch = args["--public"]
                else:
                    publicBranch = config.getPublicBranchFor(git.currentBranch())
                slot = int(slotMappings[publicBranch])
            else:
                slot = int(slot)
            if args["--minor"]:
                slot = 2
            if args["--major"]:
                slot = 1
            # extend the version number if slot comes in too large.
            while len(slots) < slot:
                slots.append(0)
            slots[slot - 1] += 1
            while slot < len(slots):
                slots[slot] = 0
                slot += 1
            # write the new version number to the version file. 
            with open(fileName, 'r+') as f:
                self.ver = self.writeVersion(f, slots, args)
            self.stageVersionFile(fileName)
            if not args["--nocommit"]:
                git.commit("-m \"GRAPE: ticked version to %s\"" % self.ver)
                
        if (not args["--nocommit"]) or args["--tag"]:
            self.tagVersion(self.ver, args)
            if args["--tagNested"]:
                cwd = os.getcwd()
                wsDir = utility.workspaceDir()
                for subproject in grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes():
                    os.chdir(os.path.join(wsDir, subproject))
                    self.tagVersion(self.ver, args)
                os.chdir(cwd)
                

    @staticmethod
    def stageVersionFile(fname):
        print ( "STAGING %s" % fname)
        git.add(fname)
        return True

    @staticmethod
    def stageGrapeconfigFile(fname):
        git.add(fname)

        return True

    @staticmethod
    def tagVersion(version, args):
        doTag = args["--updateTag"].strip().lower() == "true"
        if doTag:
            doTag = not args["--notag"]
        else:
            doTag = args["--tag"]
        if doTag:
            prefix = args["--prefix"]
            suffix = args["--suffix"]
            tagPrefix = args["--tagPrefix"]
            tagSuffix = args["--tagSuffix"]
            
            if tagPrefix and tagPrefix != prefix:
                if prefix: 
                    version.replace(prefix,tagPrefix,1)
                else: 
                    version = tagPrefix+version
            if tagSuffix and tagSuffix != suffix:
                if suffix:
                    l = len(suffix)
                    version = version[0:-l] + version[-l:].replace(suffix, tagSuffix, 1)
                else:
                    version = version + tagSuffix
                    
                
            git.tag("-a %s -m \"Tagged by grape\"" % version)
        return True

    def readVersion(self, fileName, args):
        config = grapeConfig.grapeConfig()
        prefix = args["--prefix"]
        if args["--suffix"]:
            suffix = args["--suffix"]
        else:
            try:
                suffixMapping = config.getMapping("versioning", "branchSuffixMappings")
                suffix = suffixMapping[config.getPublicBranchFor(git.currentBranch())]
            except KeyError:
                suffix = ""
        args["--suffix"] = suffix
        regex = args["--matchTo"]
        try:
            regexMappings = config.getMapping("versioning", "branchVersionRegexMappings")
            public = config.getPublicBranchFor(git.currentBranch())
            regex = regexMappings[public]
        except ConfigParser.NoOptionError:
            pass

        #tweaked from http://stackoverflow.com/questions/2020180/increment-a-version-id-by-one-and-write-to-mk-file
        regex = regex.replace("<prefix>", prefix)
        regex = regex.replace("<suffix>", suffix)
        self.r = re.compile(regex)

        VERSION_ID = None
        for l in fileName:
            m1 = self.r.match(l)
            if m1:
                VERSION_ID = map(int, m1.group(3).split("."))
                self.matchedLine = l
        if VERSION_ID is None:
            print("GRAPE: .")

        return VERSION_ID

    def versionLine(self, version):
        return self.r.sub(r'\g<1>\g<2>' + '.'.join(['%s' % v for v in version]) + r'\g<4>', self.matchedLine)

    def slotsToString(self, args, slots): 
        return args["--prefix"] + '.'.join(['%s' % v for v in slots])+args["--suffix"]
    
    def stringToSlots(self, args, string):
        prefix = args["--prefix"]
        suffix = args["--suffix"]
        if prefix: 
            # strip off the prefix
            string = ''.join(string.strip().split(prefix)[1:])
        if suffix:
            string = ''.join(string.strip().split(suffix)[:-1])
        return string.strip().split('.')
        

    def writeVersion(self, fileName, version, args):
        fileName.seek(0)
        lines = []
        if args["init"]:
            lines.append(self.versionLine(version))
        for l in fileName:
            if l == self.matchedLine:
                l = self.versionLine(version)
            lines.append(l)
        fileName.seek(0)
        fileName.writelines(lines)
        return self.slotsToString(args, version)

    def setDefaultConfig(self, config):
        """

        :type config: GrapeConfigParser
        """
        config.ensureSection("versioning")
        config.set("versioning", "file", ".grapeversion")
        config.set("versioning", "updateTag", "True")
        config.set("versioning", "branchSlotMappings", "?:2")
        config.set("versioning", "branchSuffixMappings", "?:")
        config.set("versioning", "branchTagSuffixMappings", "?:")
        config.set("versioning", "prefix", "v")
        
if __name__ is "__main__": 
    import grapeMenu
    import sys
    menu = grapeMenu.menu()
    menu.applyMenuChoice("version", sys.argv[1:])
