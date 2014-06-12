import os
import time
import tempfile
import smtplib
try:
    from email.mime.text import MIMEText
except ImportError:
    from email.MIMEText import MIMEText

import Atlassian
import utility
import grapeGit as git
import grapeMenu
import grapeConfig
import resumable
import subtree


class PublishStepFailed(Exception):
    def __init__(self, stepName):
        assert isinstance(stepName, str)
        self.stepName = stepName


class Publish(resumable.Resumable):
    """
    grape publish
    Merges/Squash-merges/Rebases the current topic branch <type>/<username>/<descr> into the public <branch>,
    where <public> is read from one of the <type>:<public> pairs found in .grapeconfig.flow.topicPrefixMappings and
    .grapeconfig.workspace.submoduleTopicPrefixMappings. The branch-dependent publish policy (merge vs. squash merge.
    vs rebase, etc) is decided using grapeconfig.flow.publishPolicy for the top-level repo and the publish policy for
    submodules is decided using grapeconfig.workspace.submodulePublishPolicy.

    Usage:  grape-publish [--squash [--cascade ] | --merge |  --rebase]
                         [-m <msg>]
                         [--recurse | --norecurse]
                         [--public=<public> [--submodulePublic=<submodulePublic>]]
                         [--topic=<branch>]
                         [--noverify]
                         [--nopush]
                         [--pushSubtrees | --noPushSubtrees]
                         [-v]
                         [--startAt=<startStep>] [--stopAt=<stopStep>]
                         [--buildCmds=<buildStr>] [--buildDir=<path>]
                         [--testCmds=<testStr>] [--testDir=<path>]
                         [--prepublishCmds=<cmds>] [--prepublishDir=<path>]
                         [--postpublishCmds=<cmds>] [--postpublishDir=<path>]
                         [--noUpdateLog | [--updateLog=<file> --skipFirstLines=<int> --entryHeader=<string>]]
                         [--tickVersion=<bool> [-T <arg>]...]
                         [--user=<StashUserName>]
                         [--project=<StashProjectKey>]
                         [--repo=<StashRepoName>]
                         [-R <arg>]...
                         [--noReview]
                         [--useStash=<bool>]
                         [--deleteTopic=<bool>]
                         [--emailNotification=<bool> [--emailHeader=<str> --emailSubject=<str> --emailSendTo=<addr>
                          --emailServer=<smtpserver>]]
                         [<CommitMessageFile>]
            grape-publish --continue
            grape-publish --abort
            grape-publish --printSteps
            grape-publish --quick -m <msg> [-v] [--user=<StashUserName>]

    Options:
    --squash                Squash merges the topic into the public, then performs a commit if the merge goes clean.
    --cascade               For squash merges, can choose to cascade back to the topic branch after the merge is
                            completed.
    --merge                 Perform a normal merge.
    -m <msg>                The commit message to use for a successful merge / squash merge. Ignored if used with
                            --rebase.
    --rebase                Rebases the topic branch to the public, then fast forwards the public to the tip of the
                            topic.
    --recurse               Perform the publish action in submodules.
                            Defaults to True if .grapeconfig.workspace.manageSubmodules is True.
    --norecurse             Do not perform the publish action in submodules.
                            Defaults to True if .grapeconfig.workspace.manageSubmodules is False.
    --topic=<branch>        The branch to publish. Defaults to the current branch.
    --noverify              Set to skip interactive verification of publish commands.
    --nopush                Set to skip the push of commits generated during the publish procedure.
    --pushSubtrees          Push subtrees to their respective remotes (.grapeconfig.subtree-<name>.remote) appropriate
                            public branches (.grapeconfig.subtree-<name>.topicPrefixMappings)
                            Set by default if .grapeconfig.subtrees.pushOnPublish is True.
    --noPushSubtrees        Don't perform a git subtree push.
    -v                      Be more verbose.
    --startAt=<startStep>   The publish step to start at. One of "build", "test", "prePublish", "tickVersion",
                            "publish", "postPublish", or "deleteTopic".
    --stopAt=<stopStep>     The publish step to stop at. Valid values are the same as for --startAt. Publish will
                            perform all steps from <startStep> (inclusive) to <stopStep> (exclusive).
    --continue              Resume a previous call to grape publish that encountered a failure at one of the publish
                            steps.
    --abort                 Abort a previously failed call to grape publish.   
    --buildCmds=<buildStr>  The comma-delimited list of build commands to execute.
                            [default: .grapeconfig.publish.buildCmds]
    --buildDir=<path>       The directory (relative to the workspace root directory) to execute the build steps in.
                            [default: .grapeconfig.publish.buildDir]
    --testCmds=<testStr>    The comma-delimited list of test commands to execute.
                            [default: .grapeconfig.publish.testCmds]
    --testDir=<path>        The directory (relative to the workspace root directory) to execute the test steps in.
                            [default: .grapeconfig.publish.testDir]
    --prepublishCmds=<str>  The comma-delimited list of commands to execute just before the publish step.
                            [default: .grapeconfig.publish.prepublishCmds]
    --prepublishDir=<str>   The directory (relative to the workspace root directory) to execute the pre-publish cmds in.
                            [default: .grapeconfig.publish.prepublishDir]
    --postpublishCmds=<str>  The comma-delimited list of commands to execute just after the publish step.
                            [default: .grapeconfig.publish.postpublishCmds]
    --postpublishDir=<str>  The directory (relative to the workspace root directory) to execute the post-publish
                            cmds in.
                            [default: .grapeconfig.publish.postpublishDir]
    --deleteTopic=<bool>    Delete the topic branch when done. [default: .grapeconfig.publish.deleteTopic]
    --noUpdateLog           Set to skip the updateLog step.
    --updateLog=<file>      The log file to update with the commit message for this branch.
                            [default: .grapeconfig.publish.updateLog]
    --skipFirstLines=<int>  The number of lines to skip in the updateLog file before inserting the commit message.
                            [default: .grapeconfig.publish.logSkipFirstLines]
    --entryHeader=<string>  The format for the commit message header. The string literals <date>, <user>, and <version>
                            will be replaced by the date, the result of git config --get user.name, and the result of
                            git describe --abbrev=0 after the tickversion step, respectively.
                            [default: .grapeconfig.publish.logEntryHeader]
    --tickVersion=<bool>    Tick a version number as a part of this publish action.
                            [default: .grapeconfig.publish.tickVersion]
    -T <arg>                An argument to pass to grape-version tick. Type grape version --help for available options
                            and defaults. -T can be used multiple times to pass multiple arguments.
    --user=<user>           Your Stash username.
    --project=<project>     Your Stash Project. See grape-review for more details.
                            [default: .grapeconfig.project.name]
    --repo=<repo>           Your Stash repo. See grape-review for more details.
                            [default: .grapeconfig.repo.name]
    -R <arg>                Argument(s) to pass to grape-review, in addition to --title="**IN PROGRES**:" --prepend.
                            Type grape review --help for valid options.
    --noReview              Don't perform any actions that interact with pull requests. Overrides --useStash.
    --useStash=<bool>       Whether or not to use pull requests. [default: .grapeconfig.publish.useStash]
    --public=<public>       The branch to publish to. Defaults to the mapping for the current topic branch as described
                            by .grapeconfig.flow.topicPrefixMappings.
    --submodulePublic=<b>   The branch to publish to in submodules. Defaults to the mapping for the current topic branch
                            as described by .grapeconfig.workspace.submoduleTopicPrefixMappings.
    --emailNotification=<b> Set to true to send a notification email after you've published. The email will consist of
                            a header <header>, and a message, generally the contents of <CommitMessageFile> and/or
                            the Pull Request description. The email is sent to <addr>, and will be CC'd to the user.
                            For the email subject and header, the string literals
                            '<user>', '<date>', '<version>', and '<public>' with the following:
                            <user>: the result of git config --get user.name
                            <date>: the current timestamp.
                            <version>: The version of the project, so long as grape is managing your versioning.
                            <public>: The branch to publish to.
                            [default: .grapeconfig.publish.emailNotification]
    --emailHeader=<header>  The email header. See above.
                            [default: .grapeconfig.publish.emailHeader]
    --emailSubject=<sbj>    The email subject. See above.
                            [default: .grapeconfig.publish.emailSubject]
    --emailSendTo=<addr>    The receiver of the email.
                            [default: .grapeconfig.publish.emailSendTo]
    --emailServer=<server>  The smtp email server address.
                            [default: .grapeconfig.publish.emailServer]
    --quick                 Perform the following steps only: ensureReview, markInProgress, publish, markAsDone

    Optional Arguments:
    <CommitMessageFile>     A file with an update message for this publish command. The pull request associated with
                            this branch will be updated to contain this message. If you don't specify a filename, it is
                            assumed that the contents of the pull request description are intended for the update
                            message. Both the commit message for the merge and an update log will contain this message.
                            Additionally, if email notification is configured, the contents of the email will have
                            this message.



    """

    def setDefaultConfig(self, config):
        config.ensureSection("workspace")
        config.ensureSection("flow")
        config.ensureSection("subtrees")
        config.ensureSection("publish")

        # workspace defaults
        config.set('workspace', 'manageSubmodules', 'True')
        config.set('workspace', 'submoduleTopicPrefixMappings', '?:develop')
        config.set('workspace', 'submodulePublishPolicy', '?:merge')
        # publish policy defaults
        config.set('flow', 'publishPolicy', '?:merge')
        # subtree publish actions
        config.set('subtrees', 'names', '')
        config.set('subtrees', 'pushOnPublish', "False")
        # build steps
        config.set('publish', 'buildCmds', '')
        config.set('publish', 'buildDir', '.')
        # test steps
        config.set('publish', 'testCmds', '')
        config.set('publish', 'testDir', '.')
        # prepublish steps
        config.set('publish', 'prepublishCmds', '')
        config.set('publish', 'prepublishDir', '.')
        # postpublish steps
        config.set('publish', 'postpublishCmds', '')
        config.set('publish', 'postpublishDir', '.')
        # tick the version?
        config.set('publish', 'tickVersion', 'False')
        # use Stash for checking Pull Request status?
        config.set('publish', 'useStash', 'True')
        # delete when done
        config.set('publish', 'deleteTopic', 'False')
        # log file
        config.set('publish', 'updateLog', '.grapepublishlog')
        config.set('publish', 'logSkipFirstLines', '0')
        config.set('publish', 'logEntryHeader', "<date> <user>\\n<version>\\n")
        # email config
        config.set('publish', 'emailNotification', 'False')
        config.set('publish', 'emailHeader', '<public> updated to <version>')
        config.set('publish', 'emailServer', 'smtp.email.server')
        config.set('publish', 'emailSendTo', 'user.list@company.com')
        config.set('publish', 'emailSubject', '<public> updated to <version>')

    def __init__(self):
        super(Publish, self).__init__()
        self._key = "publish"
        self._section = "Gitflow Tasks"
        self.branchPrefix = None
        self.modifiedSubtrees = []
        self.st_prefices = {}
        self.st_remotes = {}
        self.st_branches = {}

    def description(self):
        try:
            public = grapeConfig.grapeConfig().getPublicBranchFor(git.currentBranch())
        except git.GrapeGitError:
            public = "Unknown"
        except KeyError:
            public = "Unknown"
        return "Publish the current topic branch to %s" % public

    def _resume(self, args):
        super(Publish, self)._resume(args)
        self.execute(args)

    def _saveProgress(self, args):
        pass

    def parseArgs(self, args):
        # resolve default topic branch, ensure we are on the topic branch
        topic = args["--topic"]
        if not topic:
            topic = git.currentBranch()
        if topic != git.currentBranch():
            git.checkout(topic)
        args["--topic"] = topic

        # resolve default public branch using .grapeconfig.flow.topicPrefixMappings
        config = grapeConfig.grapeConfig()
        prefix = git.branchPrefix(topic)
        public = args["--public"]
        if not public:
            public = config.getPublicBranchFor(topic)
        args["--public"] = public
        self.branchPrefix = prefix
        # whether or not to use Stash
        if args["--useStash"].lower() == "false" and not args["--noReview"]:
            args["--noReview"] = True
        # get the Stash Username
        user = args["--user"]

        if not user and not args["--noReview"] and not args["--printSteps"]:
            args["--user"] = utility.getUserName(service="Stash")

    def abort(self, args):
        #undo any commits done since we first started
        super(Publish, self)._resume(args)
        branch = git.currentBranch()
        utility.printMsg("Reverting %s from %s to %s" % (branch, git.SHA(branch), self.progress["startingSHA"]))
        revert = utility.userInput("continue? [y,n]", "y")
        if revert:
            git.checkout("-B %s %s" % (branch, self.progress["startingSHA"]))
        # release IN PROGRESS LOCK
        utility.printMsg("Releasing In Progress Lock")
        self.releaseInProgressLock(args)

    def execute(self, args):
        if args["--abort"]: 
            self.abort(args)
        if "startingSHA" not in self.progress:
            self.progress["startingSHA"] = git.SHA("HEAD")
        self.parseArgs(args)
        
        startPoint = args["--startAt"]
        order = ["ensureReview", "verifyCompletedReview", "testForCleanWorkspace1", "verifyPublishActions",
                 "md", "markInProgress", "tickVersion", "updateLog",
                 "build", "test", "testForCleanWorkspace2", "prePublish", "publish", "postPublish",
                 "tagVersion", "markAsDone", "notify", "deleteTopic", "done"]

        if args["--quick"]:
            order = ["md", "ensureReview", "markInProgress", "publish", "markAsDone", "deleteTopic", "done"]

        if args["--printSteps"]:
            print order
            return True

        if startPoint:
            if startPoint not in order:
                utility.printMsg("%s not a valid publish step. Choose 1 of :\n %s" % (startPoint, order))
        else:
            startPoint = order[0]

        stopPoint = args["--stopAt"]

        steps = {"build": self.performCustomBuildStep,
                 "test": self.performCustomTestStep,
                 "prePublish": self.performCustomPrePublishSteps,
                 "tickVersion": self.tickVersion,
                 "tagVersion": self.tagVersion,
                 "publish": self.publishAllProjects,
                 "postPublish": self.performCustomPostPublishSteps,
                 "deleteTopic": self.deleteTopicBranch,
                 "verifyCompletedReview": self.verifyCompletedReview,
                 "testForCleanWorkspace1": self.testForCleanWorkspace,
                 "testForCleanWorkspace2": self.testForCleanWorkspace,
                 "markInProgress": self.aquireInProgressLock,
                 "markAsDone": self.releaseInProgressLock,
                 "updateLog": self.updateLog,
                 "notify": self.sendNotificationEmail,
                 "ensureReview": self.ensureReview,
                 "md": self.mergePublic,
                 "verifyPublishActions": self.verifyPublishTargetsWithUser}


        currentStep = startPoint
        for step in order:
            if step == "done":
                break
            if step == stopPoint:
                utility.printMsg("Stopping at %s step as requested." % stopPoint)
                break
            if step != currentStep:
                continue
            try:
                ret = steps[step](args)
            except BaseException as e:
                self.bailOut(step, args)
                print(e.message)
                return False
            if ret:
                currentStep = order[order.index(currentStep) + 1]
            else:
                self.bailOut(step, args)
                return False

        return True

    def bailOut(self, step, args):
        utility.printMsg("Publish step %s failed. Please resolve the issue and then continue using\n"
                         "grape publish --continue" % step.upper())
        args["--startAt"] = step
        self.dumpProgress(args)
        return

    def mergePublic(self, args):
        menu = grapeMenu.menu()
        return menu.applyMenuChoice("md", ["--am", "--public=%s" % args["--public"]])

    @staticmethod
    def markReview(args, newArgs, skipStr, updateOnly=True):
        if args["--noReview"]:
            utility.printMsg(skipStr)
            return True
        reviewArgs = args["-R"]
        finalArgs = []
        if updateOnly:
            finalArgs = ["--update"]
        finalArgs += ["--source=%s" % args["--topic"], "--target=%s" % args["--public"],
                      "--user=%s" % args["--user"]]
        if len(newArgs) > 0:
            finalArgs += newArgs
        for arg in reviewArgs:
            finalArgs.append(arg.strip())
        return grapeMenu.menu().applyMenuChoice("review", finalArgs)

    def markReviewAsInProgress(self, args):
        utility.printMsg("Prepending pull request title with **IN PROGRESS**...")
        return self.markReview(args, ["--title=**IN PROGRESS** ", "--prepend"], "Skipping marking pull request "
                                                                                "as IN PROGRESS...")

    def markReviewWithVersionNumber(self, args):
        version = self.progress["version"]
        utility.printMsg("Prepending pull request title with %s" % version)
        return self.markReview(args, ["--title=%s :" % version, "--prepend"], "Skipping marking pull request with "
                                                                              "version number")

    def ensureReview(self, args):
        return self.markReview(args, [], "Skipping ensuring review exists.", updateOnly=False)

    @staticmethod
    def checkInProgressLock(args):
        if args["--noReview"]:
            utility.printMsg("Skipping In Progresss Lock Check..")
            return True
        atlassian = Atlassian.Atlassian(username=args["--user"])
        repo = atlassian.project(args["--project"]).repo(args["--repo"])
        pullRequests = repo.pullrequests()
        inProgressRequests = []
        for request in pullRequests:
            inProgress = "IN PROGRESS" in request.title()
            if inProgress:
                doesConflict = request.toRef() == args["--public"]
                if doesConflict:
                    inProgressRequests.append(request)
        if len(inProgressRequests) == 0:
            utility.printMsg("No other pull requests are IN PROGRESS...")
            return True
        elif len(inProgressRequests) == 1:
            thisRequest = repo.getOpenPullRequest(args["--topic"], args["--public"])
            if thisRequest == inProgressRequests[0]:
                utility.printMsg("The pull request for this branch is already in progress. Continuing...")
                return 2
            else:
                utility.printMsg("The following pull request is already in progress:")
                print(inProgressRequests[0])
                return False
        else:
            utility.printMsg("ERROR: There are multiple pull requests in progress!")
            for request in inProgressRequests:
                print request
            return False

    def aquireInProgressLock(self, args):
        if args["--noReview"]:
            utility.printMsg("Skipping In Progresss Lock Check..")
            return True
        retcode = self.checkInProgressLock(args)
        if retcode:
            # the 2 means we are already marked as in progress
            return ((retcode == 2) or self.markReviewAsInProgress(args)) and self.checkInProgressLock(args)
        else:
            return False

    def releaseInProgressLock(self, args):
        if args["--noReview"]:
            utility.printMsg("Skipping verification of code review...")
            return True
        atlassian = Atlassian.Atlassian(username=args["--user"])
        repo = atlassian.project(args["--project"]).repo(args["--repo"])
        request = repo.getOpenPullRequest(args["--topic"], args["--public"])
        if not request:
            matchingRequests = repo.getMergedPullRequests(args["--topic"], args["--public"])
            for r in matchingRequests:
                if "**IN PROGRESS**" in r.title():
                    request = r
                    break
        if request:
            title = request.title().replace("**IN PROGRESS**", "")
            return self.markReview(args, ["--title=%s" % title, "--state=merged"], "")
        else:
            utility.printMsg("WARNING: No Open or Merged IN PROGRESS pull request found. Continuing...")
        return True

    @staticmethod
    def verifyCompletedReview(args):
        if args["--noReview"]:
            utility.printMsg("Skipping verification of code review...")
            return True
        atlassian = Atlassian.Atlassian(username=args["--user"])
        repo = atlassian.project(args["--project"]).repo(args["--repo"])
        pullRequest = repo.getOpenPullRequest(args["--topic"], args["--public"])
        verified = False
        if pullRequest:
            verified = pullRequest.approved()
            if not verified:
                reviewers = pullRequest.reviewers()
                print reviewers
                if not reviewers:
                    utility.printMsg("There are no reviewers for your pull request for %s targeting %s." %
                                     (args["--topic"], args["--public"]))
                else:
                    utility.printMsg("The following reviewers have not approved your request:\n")
                    for reviewer in reviewers:
                        if reviewer[1] is False:
                            print(reviewer[0], reviewer[1])
            else:
                utility.printMsg("All reviewers have approved your request.")
        else:
            utility.printMsg("There is no pull request for your current branch. \nStart one using grape review or by "
                             "visiting %s" % ('/'.join([atlassian.url, "projects", args["--project"], "repos",
                                                        args["--repo"], "pull-requests"])))
        return verified

    @staticmethod
    def testForCleanWorkspace(args):
        utility.printMsg("Checking to make sure workspace has a clean status.")
        cwd = os.getcwd()
        os.chdir(utility.workspaceDir())
        ret = git.isWorkingDirectoryClean()
        os.chdir(cwd)
        return ret

    def performCustomStep(self, prefix, args):
        if not args["--%sCmds" % prefix]:
            return True
        cwd = os.getcwd()
        if args["--%sDir" % prefix]:
            os.chdir(os.path.join(utility.workspaceDir(), args["--%sDir" % prefix]))
        cmds = args["--%sCmds" % prefix].split(',')
        ret = True
        utility.printMsg("GRAPE PUBLISH - PERFORMING CUSTOM %s STEP" % prefix.upper())
        for cmd in cmds:
            if ret:
                if "<version>" in cmd:
                    self.loadVersion(args)
                    verStr = self.progress["version"]
                    cmd = cmd.replace("<version>", verStr)
                returnCode = utility.executeSubProcess(cmd.strip(), workingDirectory=os.getcwd()).returncode
                print(returnCode)
                ret = ret and (returnCode == 0)
                if not ret: 
                    break
        os.chdir(cwd)
        return ret

    def performCustomBuildStep(self, args):
        return self.performCustomStep("build", args) and self.checkInProgressLock(args)

    def performCustomTestStep(self, args):
        return self.performCustomStep("test", args) and self.checkInProgressLock(args)

    def performCustomPrePublishSteps(self, args):
        ret = self.performCustomStep("prepublish", args)
        if not ret:
            return ret
        self.loadModifiedFiles(args)
        try:
            git.commit(" -m \"GRAPE PUBLISH: committing staged file changes before publish.%s\"")
        except git.GrapeGitError:
            pass
        return self.checkInProgressLock(args)

    def performCustomPostPublishSteps(self, args):
        return self.performCustomStep("postpublish", args)

    def loadModifiedFiles(self, args):
        if "modifiedFiles" in self.progress:
            return True
        public = args["--public"]
        topic = args["--topic"]
        if git.SHA(public) == git.SHA(topic):
            public = utility.userInput("Please enter the branch name or SHA of the commit to diff against %s for the "
                                       "modified file list." % topic)
        self.progress["modifiedFiles"] = git.diff("--name-only %s %s" % (public, topic)).split('\n')
        return True

    def loadVersion(self, args):
        if "version" in self.progress:
            return True
        else:
            self.progress["version"] = utility.userInput("Please enter version string for this commit")
        return True

    def loadCommitMessage(self, args):
        if "commitMsg" in self.progress:
            return True
        if args["--noUpdateLog"]:
            self.progress["commitMsg"] = "no details entered"
            return True

        if not args["<CommitMessageFile>"] and not args["-m"]:
            proceed = utility.userInput("No commit message entered. Would you like to use the Pull Request's "
                                        "description as your  commit message? [y/n]", 'y')
            if not proceed:
                args["<CommitMessageFile>"] = utility.userInput("Enter the name of the file containing your commit "
                                                                "message: ")

        if args["<CommitMessageFile>"]:
            commitMsgFile = args["<CommitMessageFile>"]
            try:
                with open(commitMsgFile, 'r') as f:
                    commitMsg = f.readlines()

            except IOError as e:
                print(e.message)
                utility.printMsg("Could not read contents of %s" % commitMsgFile)
                args["<CommitMessageFile>"] = False 
                return False

            if not args["--noReview"]:
                utility.printMsg("Updating Pull Request with commit msg...")
                self.markReview(args, ["--descr", commitMsgFile], "")
            else:
                utility.printMsg("Skipping update of pull request description from commit message")
        else:
            if args["--noReview"]:
                utility.printMsg("Skipping retreival of commit message from Pull Request description..")
                if not args["-m"]:
                    print("File with commit message is required argument when publishing with --noReview and no -m "
                          "<msg> defined.")
                    return False
            utility.printMsg("Retrieving pull request description for use as commit message...")
            atlassian = Atlassian.Atlassian(username=args["--user"])
            repo = atlassian.project(args["--project"]).repo(args["--repo"])
            pullRequest = repo.getOpenPullRequest(args["--topic"], args["--public"])
            commitMsg = pullRequest.description().splitlines(True)+['']

        # this will be used for the actual merge commit message.
        escapedCommitMsg = ''.join(commitMsg).replace("\"", "\\\"")
        escapedCommitMsg = escapedCommitMsg.replace("`", "'")
        
        if escapedCommitMsg and not args["-m"]:
            args["-m"] = escapedCommitMsg
        elif not escapedCommitMsg and args["-m"]:
            escapedCommitMsg = args["-m"]
            commitMsg = [args["-m"]]
        else:
            utility.printMsg("WARNING: Commit message is empty. ")

        utility.printMsg("The following commit message will be used for email notification, merge commits, etc.\n "
                         "======================================================================")
        print ''.join(commitMsg[:10])
        print "======================================================================"
        proceed = utility.userInput("Is the above message what you want for email notifications and merge commits? "
                                    "['y','n']", 'y')
        if not proceed:
            utility.printMsg("Stopping. Either edit the message in your pull request, or pass in the name of a file "
                             "containing your message as an argument to grape publish.")
            e = Exception()
            e.message = "Invalid commit message."
            args["<CommitMessageFile>"] = False
            args["-m"] = False
            raise e
        else:
            self.progress["commitMsg"] = escapedCommitMsg
            return True

    def updateLog(self, args):
        if not (self.loadCommitMessage(args) and self.loadVersion(args)):
            return False
        commitMsg = self.progress["commitMsg"].split('\n')

        if args["--noUpdateLog"]:
            return True
        logFile = args["--updateLog"]
        cwd = os.getcwd()
        os.chdir(git.baseDir())
        if logFile:
            header = args["--entryHeader"]
            header = header.replace("<date>", time.asctime())
            header = header.replace("<user>", git.config("--get user.name"))
            header = header.replace("<version>", self.progress["version"])
            header = header.split("\\n")
            commitMsg = header + commitMsg
            numLinesToSkip = int(args["--skipFirstLines"])
            with open(logFile, 'r') as f:
                loglines = f.readlines()
            loglines.insert(numLinesToSkip, '\n'.join(commitMsg))
            with open(logFile, 'w') as f:
                f.writelines(loglines)
            git.commit("%s -m \"GRAPE publish: updated log file %s\"" % (logFile, logFile))
        os.chdir(cwd)
        return self.checkInProgressLock(args)

    def tickVersion(self, args):
        ret = True
        if args["--tickVersion"].lower() == "true":
            versionArgs = ["tick", "--notag"]
            for arg in args["-T"]:
                versionArgs += [arg.strip()]
            ret = grapeMenu.menu().applyMenuChoice("version", versionArgs)
            self.progress["version"] = grapeMenu.menu().getOption("version").ver
            ret = ret and self.markReviewWithVersionNumber(args)
        return ret and self.checkInProgressLock(args)

    @staticmethod
    def tagVersion(args):
        ret = True
        if args["--tickVersion"].lower() == "true":
            versionArgs = ["tick", "--tag", "--notick", "--nocommit"]
            for arg in args["-T"]:
                versionArgs += [arg.strip()]
            ret = grapeMenu.menu().applyMenuChoice("version", versionArgs)
            git.push("--tags origin")
        return ret

    def sendNotificationEmail(self, args):

        if not args["--emailNotification"].lower() == "true":
            # skip email send
            return True
        if not (self.loadCommitMessage(args) and self.loadVersion(args) and self.loadModifiedFiles(args)):
            return False
        # Write the contents of the mail file out to a temporary file
        mailfile = tempfile.mktemp()
        mf = open(mailfile, 'w')

        date = time.asctime()
        emailHeader = args["--emailHeader"]
        emailHeader = emailHeader.replace("<user>", git.config("--get user.name"))
        emailHeader = emailHeader.replace("<date>", date)
        emailHeader = emailHeader.replace("<version>", self.progress["version"])
        emailHeader = emailHeader.replace("<public>", args["--public"])
        emailHeader = emailHeader.split("\\n")
        mf.write('\n'.join(emailHeader))
        comments = self.progress["commitMsg"]
        mf.write(comments)
        updatelist = self.progress["modifiedFiles"]
        if len(updatelist) > 0:
            mf.write("\n FILES UPDATED:\n")
            mf.write("\n".join(updatelist))
        mf.close()

        # Open the file back up and attach it to a MIME message
        t = open(mailfile, 'rb')
        message = t.read()
        t.close()
        msg = MIMEText(message)

        # Use their email address from their git user profile.
        myemail = git.config("--get user.email")
        mailsubj = args["--emailSubject"]
        mailsubj = mailsubj.replace("<user>", git.config("--get user.name"))
        mailsubj = mailsubj.replace("<public>", args["--public"])
        mailsubj = mailsubj.replace("<version>", self.progress["version"])
        mailsubj = mailsubj.replace("<date>", date)
        sendto = args["--emailSendTo"]
        msg['Subject'] = mailsubj
        msg['From'] = myemail
        msg['To'] = sendto
        msg['CC'] = myemail

        # Send the message via the configured SMTP server (don't know if this
        # is necessary - localhost might work just as well)
        import socket
        try:
            s = smtplib.SMTP("nospam.llnl.gov", timeout=10)
        except socket.error, e:
            utility.printMsg("Failed to email: %s" % str(e))
            return False

        # Don't need to connect if we specified the
        # host in the SMTP constructor above...
        #s.connect()
        s.sendmail(msg['From'], [sendto, myemail], msg.as_string())
        s.quit()

        # Remove the tempfile
        os.remove(mailfile)

        return True

    @staticmethod
    def deleteTopicBranch(args):
        if args["--deleteTopic"].lower() == "true":
            grapeMenu.menu().applyMenuChoice("db", [args["--topic"]])
        return True

    @staticmethod
    def validateInput(policy, args):
        policy = policy.strip().lower()
        valid = False
        if policy == "merge" or policy == "squash":
            valid = bool(args["-m"])
            if not valid:
                print("Commit message required for merge or squash merge publish policies.")
        if policy == "rebase":
            valid = True
        if not valid:
            print("Type grape publish -h for more details")
        return valid

    @staticmethod
    def merge(public, topic, args):
        print("merging %s into %s" % (topic, public))
        git.checkout(public)
        git.merge("%s -m \"%s\" " % (topic, args["-m"]))
        print("%s merged successfully to %s" % (topic, public))
        print("You are currently on %s" % public)

    @staticmethod
    def squashMerge(public, topic, args):
        print("squash merging %s into %s" % (topic, public))
        git.checkout(public)
        git.merge("--squash %s" % topic)
        git.commit("-m \"%s\"" % args["-m"])
        print("%s squash-merged successfully to %s" % (topic, public))
        print("You are currently on %s" % public)
        if args["--cascade"]:
            git.checkout(topic)
            git.merge("%s -m \"GRAPE PUBLISH: cascade merge of %s to %s after publish.\"" % (public, public, topic))

    @staticmethod
    def rebase(public, topic):
        print("rebasing %s onto %s" % (topic, public))
        git.rebase(public)
        print("%s successfully rebased onto %s" % (topic, public))
        git.checkout(public)
        git.merge(topic)
        print("You are currently on %s" % public)

    def publish(self, policy, public, topic, args):
        # don't bother publishing if public and topic are the same commit
        if git.shortSHA(public, quiet=True).strip() == git.shortSHA(topic, quiet=True).strip():
            git.checkout(public)
            return
        policy = policy.strip().lower()
        if policy == "merge":
            self.merge(public, topic, args)
        elif policy == "squash":
            self.squashMerge(public, topic, args)
        elif policy == "rebase":
            self.rebase(public, topic)

        if not args["--nopush"]:
            git.push("-u origin HEAD")

    def loadPublishTargets(self, args):
        config = grapeConfig.grapeConfig()
        public = args["--public"]
        topic = args["--topic"]
        quiet = args["-v"]
        # decide whether to recurse into submodules
        recurse = grapeConfig.grapeConfig().get('workspace', 'manageSubmodules')
        if args["--recurse"]:
            recurse = True
        if args["--norecurse"]:
            recurse = False

        # no need to recurse if there are no modified submodules
        submodules = git.getModifiedSubmodules(public, topic)
        args["--recurse"] = recurse and submodules
        if args["--recurse"]:
            if not args["--submodulePublic"]:
                submapping = config.getMapping('workspace', 'submoduleTopicPrefixMappings')
                submodulePublic = submapping[self.branchPrefix]
                args["--submodulePublic"] = submodulePublic

        # deal with subtrees
        push_subtrees = config.getboolean("subtrees", 'pushOnPublish') or args["--pushSubtrees"]
        push_subtrees = push_subtrees and not args["--noPushSubtrees"]
        args["--pushSubtrees"] = push_subtrees
        if push_subtrees:
            allsubtrees = config.get('subtrees', 'names').strip().split()

            for st in allsubtrees:
                prefix = config.get('subtree-%s' % st, 'prefix')
                if git.diff("--name-only %s %s -- %s" % (public, topic, prefix), quiet=quiet):
                    self.modifiedSubtrees.append(st)
            for st in self.modifiedSubtrees:
                self.st_prefices[st] = config.get('subtree-%s' % st, 'prefix')
                self.st_remotes[st] = subtree.parseSubtreeRemote(config.get('subtree-%s' % st, 'remote'))
                self.st_branches[st] = config.getMapping('subtree-%s' % st, 'topicPrefixMappings')[topic]
        return True

    def verifyPublishTargetsWithUser(self, args):
        if args["--noverify"]:
            return True
        if "targetsVerified" in self.progress and self.progress["targetsVerified"]:
            return True
        if not self.loadPublishTargets(args):
            return False
        recurse = args["--recurse"]
        public = args["--public"]
        topic = args["--topic"]
        submodules = git.getModifiedSubmodules(public, topic)
        if recurse:
            proceed = utility.userInput("When ready, grape will publish " + topic + " to "
                                        + args["--submodulePublic"] +
                                        " for the following submodules:\n%s\n " % '\n'.join(submodules) +
                                        "\n and %s to %s for the outer level repo. Proceed? [y/n]" % (topic, public),
                                        'y')
            if not proceed:
                return False
        else:
            proceed = utility.userInput("When ready, grape will publish %s to %s for the outer level repo. "
                                        "Proceed? [y/n]" % (topic, public), 'y')

            if not proceed:
                return False

        push_subtrees = args["--pushSubtrees"]
        if push_subtrees:
            if self.modifiedSubtrees:
                utility.printMsg("When ready, grape will publish the following subtrees to the following destinations:")
                for st in self.modifiedSubtrees:
                    print("subtree: %s\trepo: %s\tbranch:%s" % (self.st_prefices[st], self.st_remotes[st],
                                                                self.st_branches[st]))
                proceed = utility.userInput("Proceed? [y/n]", 'y')
                if not proceed:
                    return False
        self.progress["targetsVerified"] = True
        return True

    def publishAllProjects(self, args):
        # make sure we have a commit message
        quiet = not args["-v"]
        if not (self.loadCommitMessage(args) and self.loadPublishTargets(args)):
            return False
        public = args["--public"]
        topic = args["--topic"]
        recurse = args["--recurse"]
        config = grapeConfig.grapeConfig()

        # make sure public branches are up to date.
        grapeMenu.menu().applyMenuChoice('up', ['up'])

        # set any CL defined publish policy
        policy = None
        if args["--merge"]:
            policy = "merge"
        if args["--squash"]:
            policy = "squash"
        if args["--rebase"]:
            policy = "rebase"

        cwd = git.baseDir(quiet=quiet)
        os.chdir(cwd)

        if recurse:
            submodulePublic = args["--submodulePublic"]
            submodules = git.getModifiedSubmodules(public, topic)
            # submodule policy is Command Line requested policy, otherwise is based on 
            #       .grapeconfig.workspace.submodulePublishPolicy
            submodulePolicy = policy
            # store current value for args["--cascade"]
            outerCascadeOption = args["--cascade"]
            if not submodulePolicy:
                submodulePolicy = config.getMapping('workspace', 'submodulePublishPolicy')[submodulePublic]
                if submodulePolicy == "cascade":
                    submodulePolicy = "squash"
                    args["--cascade"] = True
            valid = self.validateInput(submodulePolicy, args)
            if valid and self.verifyPublishTargetsWithUser(args):
                for sub in submodules:
                    os.chdir(os.path.join(cwd, sub))

                    grapeMenu.menu().applyMenuChoice('up', ['up', '--public=%s' % submodulePublic])
                    self.publish(submodulePolicy, submodulePublic, topic, args)
            # restore value for args[--cascade]
            args["--cascade"] = outerCascadeOption
            os.chdir(cwd)

        # push subtrees to their respective remote branches
        push_subtrees = args["--pushSubtrees"]
        if push_subtrees:

            allsubtrees = config.get('subtrees', 'names').strip().split()
            modifiedSubtrees = []
            for st in allsubtrees:
                prefix = config.get('subtree-%s' % st, 'prefix')
                if git.diff("--name-only %s %s -- %s" % (public, topic, prefix), quiet=quiet): 
                    modifiedSubtrees.append(st)
            if modifiedSubtrees: 

                proceed = self.verifyPublishTargetsWithUser(args)
                if proceed:
                    squash = "--squash" if config.get("subtrees", "mergepolicy").lower() == "squash" else ""
                    for st in modifiedSubtrees:
                        print("%s pushing subtree %s to %s (branch %s)..." % (squash, self.st_prefices[st],
                                                                              self.st_remotes[st], self.st_branches[st]))

                        try:
                            git.subtree("push %s --prefix=%s %s %s -m \"%s\"" % (squash, self.st_prefices[st],
                                                                                 self.st_remotes[st],  self.st_branches[st],
                                                                                 args["-m"]), quiet=quiet)
                        except git.GrapeGitError:
                            # the push can fail if there has never been a subtree add / pull in this repo.
                            utility.printMsg("First attempt failed. Attempting a subtree pull then push...")
                            git.subtree("pull %s --prefix=%s %s %s -m \"%s\"" % (squash, self.st_prefices[st],
                                                                                 self.st_remotes[st], self.st_branches[st],
                                                                                 args["-m"]), quiet=quiet)
                            git.subtree("push %s --prefix=%s %s %s -m \"%s\"" % (squash, self.st_prefices[st],
                                                                                 self.st_remotes[st], self.st_branches[st],
                                                                                 args["-m"]), quiet=quiet)
                            utility.printMsg("Succeeded!")

        # update policy from config if not set on CL
        if not policy:
            policy = config.getMapping('flow', 'publishPolicy')[public]
            if policy.strip().lower() == "cascade":
                policy = "squash"
                args["--cascade"] = True
        valid = self.validateInput(policy, args)
        if valid and self.verifyPublishTargetsWithUser(args):
            self.publish(policy, public, topic, args)
            return True
        else:
            return False
