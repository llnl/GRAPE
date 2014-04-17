import option, utility
import grapeGit as git
import os
import re
import StringIO
import grapeMenu
import ConfigParser
import grapeConfig


class Version(option.Option):
    """
    grape version
    This command is used for projects that wish to have their version numbers managed by grape.

    Usage: grape-version init <version> --file=<path> [--matchTo=<str>] [--prefix=<verPrefix>]
                                                      [--tag | --notag | --updateTag=<bool>]
           grape-version tick [--major | --minor | --slot=<int>] [--tag | --notag | --updateTag=<bool>]
                              [--matchTo=<matchTo>] [--prefix=<prefix>] [--file=<path>]

    Arguments:
        <version>           Used by grape version init, this is the initial version that grape will start counting from.

    Options:
        --file=<path>       The file to store the version number. When used with init, this is mandatory, and
                            grape will update your .grapeconfig file for future version number lookups.
                            [default: .grapeconfig.versioning.file]
        --matchTo=<matchTo> The string to match to before reaching the version descriptor. Grape looks for version
                            strings matching (<matchTo>\s*=\s*)(<prefix>)(\S+)'
                            [default: VERSION_ID]
        --prefix=<prefix>   The version number prefix, such as the 'v' in v1.2.3.
                            [default: v]
        --major             Tick the Major (1st) version number.
        --minor             Tick the Minor (2nd) version number.
        --slot=<int>        Tick the <int>'th version number. 1 = Major, 2 = Minor, 3 = third, etc. If <int> is bigger
                            than the current max number of digits, the version number will be extended to have <int>
                            digits.
        --updateTag=<bool>  If true, update the version git annotated tag. [default: .grapeconfig.versioning.updateTag]
        --tag               Forces updateTag to be True.
        --notag             Forces updateTag to be False.

    """
    def __init__(self):
        super(Version, self).__init__()
        self._key = "version"
        self._section = "Gitflow Tasks"

    def description(self):
        return "Update the version for your current project."

    def execute(self, args):
        print(args)
        if args["init"]:
            self.initializeVersioning(args)
        if args["tick"]:
            self.tickVersion(args)
        return True

    def initializeVersioning(self, args):
        config = grapeConfig.grapeConfig()
        version = StringIO.StringIO()
        version.write("VERSION_ID = %s" % args["<version>"])
        version.seek(0)
        version = self.readVersion(version)
        if args["--file"]:
            fname = args["--file"]
            with open(fname, 'w') as f:
                version = self.writeVersion(f, version)
            self.stageVersionFile(fname, args)
            config.set("versioning", "file", fname)
            configFile = os.path.join(git.baseDir(), ".grapeconfig")
            grapeConfig.writeConfig(config, configFile)
            self.stageGrapeconfigFile(configFile, args)
            git.commit("%s %s -m \"GRAPE: added initial version info file %s\"" % (fname, configFile, fname))
            self.tagVersion(version, args)


    def tickVersion(self, args):
        config = grapeConfig.grapeConfig()
        file = config.get("versioning", "file")
        with open(file) as f:
            slots = self.readVersion(f)
        slot = 2
        if args["--major"]:
            slot = 1
        elif args["--slot"]:
            slot = int(args["--slot"])
        # extend the version number if slot comes in too large.
        while len(slots) < slot:
            slots.append(0)
        slot = slot -1
        slots[slot] += 1
        slot+=1
        while slot < len(slots):
            slots[slot] = 0
            slot += 1

        with open(file, 'w') as f:
            ver = self.writeVersion(f, slots)
        self.stageVersionFile(file, args)
        git.commit("-m \"GRAPE: ticked version to %s\"" % ver)
        self.tagVersion(ver, args)

    def stageVersionFile(self, fname, args):
        git.add(fname)
        return True

    def stageGrapeconfigFile(self, fname, args):
        git.add(fname)
        return True

    def tagVersion(selfself,version,args):
        doTag = args["--updateTag"].strip().lower() == "true"
        if doTag:
            doTag = not args["--notag"]
        else:
            doTag = args["--tag"]
        if doTag:
            git.tag("-a %s -m \"Tagged by grape\"" % version)
        return True


    def readVersion(self, file, idString="VERSION_ID", prefix = "v"):
        #tweaked from http://stackoverflow.com/questions/2020180/increment-a-version-id-by-one-and-write-to-mk-file
        self.r = re.compile(r'(%s\s*=\s*)(%s)(\S+)'% (idString, prefix))

        VERSION_ID = None
        for l in file:
            m1 = self.r.match(l)
            if m1:
                VERSION_ID = map(int, m1.group(3).split("."))
                self.matchedLine = l
        if VERSION_ID is None:
            print("GRAPE: string not found.")

        return VERSION_ID

    def writeVersion(self, file, version, idString="VERSION_ID", prefix="v"):

        l = self.r.sub(r'\g<1>\g<2>' + '.'.join(['%s' % (v) for v in version]), self.matchedLine)+"\n"
        file.write(l)
        verStr = ("%s" % prefix) + '.'.join(['%s' % (v) for v in version])
        return verStr

    def setDefaultConfig(self, config):
        """

        :type config: ConfigParser
        """
        grapeConfig.ensureSection(config, "versioning")
        config.set("versioning", "file", ".grapeversion")
        config.set("versioning", "updateTag", "True")


