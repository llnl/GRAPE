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

    Usage: grape-version init <version> [--file=<path>]
           grape-version tick [--major | --minor | --slot=<int>] [--tag | --notag | --updateTag=<bool>]

    Arguments:
        <version>           Used by grape version init, this is the initial version that grape will start counting from.

    Options:
        --file=<path>       The file to store the version number. [default: .grapeconfig.versioning.file]
        --major             Tick the Major (1st) version number.
        --minor             Tick the Minor (2nd) version number.
        --slot=<int>        Tick the <int>'th version number. 1 = Major, 2 = Minor, 3 = third, etc.
        --updateTag=<bool>  Update the version git annotated tag.

    """
    def __init__(self):
        self._key = "version"
        self._section = "Gitflow Tasks"
        super(Version, self).__init__()

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
        version.write("VERSION_ID = v%s" % args["<version>"])
        version.seek(0)
        version = self.readVersion(version)
        if args["--file"]:
            fname = args["--file"]
            self.writeVersion(fname, version)
            with open(fname, 'w') as f:
                f.write(version)
            git.add(f)
            config.set("versioning", "file", fname)
            grapeConfig.writeConfig(config, os.path.join(git.baseDir(), ".grapeconfig"))
            git.commit("%s .grapeconfig -m \"GRAPE: added initial version info file %s\"" % file)
        git.tag("-a %s -m \"Tagged by grape init %s\"" % (version, version))

    def tickVersion(self, args):
        config = grapeConfig.grapeConfig()
        file = config.get("versioning", "file")
        slots = self.readVersion(file)
        with open(file) as f:
            currentVersion = f.readall()

    def readVersion(self, file, idString="VERSION_ID"):
        #tweaked from http://stackoverflow.com/questions/2020180/increment-a-version-id-by-one-and-write-to-mk-file
        self.r = re.compile(r'(%s\s*=\s*)(\w*)(\S+)'% (idString))


        for l in file:
            m1 = self.r.match(l)
            if m1:
                VERSION_ID = map(int,m1.group(3).split("."))
                self.matchedLine = l
        return VERSION_ID

    def writeVersion(self, file, version, idString="VERSION_ID"):
        version[2] += 1 # increment version
        l = self.r.sub(r'\g<1>' + '.'.join(['%s' % (v) for v in version]), self.matchedLine)+"\n"
        file.write(l)

    def setDefaultConfig(self, config):
        """

        :type config: ConfigParser
        """
        grapeConfig.ensureSection(config, "versioning")
        config.set("versioning", "file", ".grapeversion")


