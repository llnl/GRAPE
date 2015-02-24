import os
import time
import tempfile
import traceback
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



class PublishStepFailed(Exception):
    def __init__(self, stepName):
        assert isinstance(stepName, str)
        self.stepName = stepName


class Publish(resumable.Resumable):
    """
    grape publish
    Merges/Squash-merges/Rebases the current topic branch <type>/<username>/<descr> into the public <branch>,
    where <public> is read from one of the <type>:<public> pairs found in .grapeconfig.flow.topicPrefixMappings,
    .grapeconfig.flow.topicDestinationMappings, and/or .grapeconfig.workspace.submoduleTopicPrefixMappings. The
    branch-dependent publish policy (merge vs. squash merge. vs rebase, etc) is decided using
    grapeconfig.flow.publishPolicy for the top-level repo and the publish policy for
    submodules is decided using grapeconfig.workspace.submodulePublishPolicy.

    Usage:  grape-publish [--squash [--cascade=<branch>... ] | --merge |  --rebase]
                         [-m <msg>]
                         [--recurse | --norecurse]
                         [--public=<public> [--submodulePublic=<submodulePublic>]]
                         [--topic=<branch>]
                         [--noverify]
                         [--nopush]
                         [--pushSubtrees | --noPushSubtrees]
                         [--forcePushSubtree=<subtreeName>]...
                         [-v]
                         [--startAt=<startStep>] [--stopAt=<stopStep>]
                         [--buildCmds=<buildStr>] [--buildDir=<path>]
                         [--testCmds=<testStr>] [--testDir=<path>]
                         [--prepublishCmds=<cmds>] [--prepublishDir=<path>]
                         [--postpublishCmds=<cmds>] [--postpublishDir=<path>]
                         [--noUpdateLog | [--updateLog=<file> --skipFirstLines=<int> --entryHeader=<string>]]
                         [--tickVersion=<bool> [-T <arg>]...]
                         [--user=<StashUserName>]
                         [--stashURL=<httpsURL>]
                         [--verifySSL=<bool>]
                         [--project=<StashProjectKey>]
                         [--repo=<StashRepoName>]
                         [-R <arg>]...
                         [--noReview]
                         [--useStash=<bool>]
                         [--deleteTopic=<bool>]
                         [--emailNotification=<bool> [--emailHeader=<str> --emailSubject=<str> --emailSendTo=<addr>
                          --emailServer=<smtpserver> --emailMaxFiles=<int>]]
                         [<CommitMessageFile>]
            grape-publish --continue
            grape-publish --abort
            grape-publish --printSteps
            grape-publish --quick -m <msg> [-v] [--user=<StashUserName>] [--public=<public>] [--noReview]

    Options:
    --squash                Squash merges the topic into the public, then performs a commit if the merge goes clean.
    --cascade=<branch>      For squash merges, can choose to cascade back to <branch> after the merge is
                            completed. Define multiple times to setup a chain of cascades. Overrides outer repo and 
                            nestedSubproject cascades defined in .grapeconfig publish policies. Does not override
                            submodule publish policies. 
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
    --stashURL=<url>        Your Stash URL, e.g. https://rzlc.llnl.gov/stash .
                            [default: .grapeconfig.project.stashURL]
    --verifySSL=<bool>      Set to False to ignore SSL certificate verification issues.
                            [default: .grapeconfig.project.verifySSL]
    --project=<project>     Your Stash Project. See grape-review for more details.
                            [default: .grapeconfig.project.name]
    --repo=<repo>           Your Stash repo. See grape-review for more details.
                            [default: .grapeconfig.repo.name]
    -R <arg>                Argument(s) to pass to grape-review, in addition to --title="**IN PROGRES**:" --prepend.
                            Type grape review --help for valid options.
    --noReview              Don't perform any actions that interact with pull requests. Overrides --useStash.
    --useStash=<bool>       Whether or not to use pull requests. [default: .grapeconfig.publish.useStash]
    --public=<public>       The branch to publish to. Defaults to the mapping for the current topic branch as described
                            by .grapeconfig.flow.topicDestinationMappings. .grapeconfig.flow.topicPrefixMappings is used
                            if no option for .grapeconfig.flow.topicDestinationMappings exists.
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
    --emailSendTo=<addr>    The comma-delimited list of receivers of the email.
                            [default: .grapeconfig.publish.emailSendTo]
    --emailServer=<server>  The smtp email server address.
                            [default: .grapeconfig.publish.emailServer]
    --emailMaxFiles=<int>   Maximum number of modified files (per subproject) to show in email.
                            [default: .grapeconfig.publish.emailMaxFiles]
    --quick                 Perform the following steps only: ensureReview, markInProgress, publish, markAsDone

    Optional Arguments:
    <CommitMessageFile>     A file with an update message for this publish command. The pull request associated with
                            this branch will be updated to contain this message. If you don't specify a filename, grape
                            will give you an opportunity to use contents of the pull request description are intended for the update
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
        config.set('publish', 'emailMaxFiles', '100')

    def __init__(self):
        super(Publish, self).__init__()
        self._key = "publish"
        self._section = "Gitflow Tasks"
        self.branchPrefix = None
        self.modifiedSubtrees = set()
        self.st_prefixes = {}
        self.st_remotes = {}
        self.st_branches = {}
        self.cascadeDict = {}

    def description(self):
        try:
            current = git.currentBranch()
            public = grapeConfig.grapeConfig().getPublicBranchFor(git.currentBranch())
        except git.GrapeGitError:
            public = "Unknown"
            current = "Unknown"
        except KeyError:
            public = "Unknown"
            current = "Unknown"
        return "Publish the current %s branch to %s" % (git.branchPrefix(current), public)

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
        if not args["--noReview"] and type(args["--verifySSL"]) != bool:
            verify = True if args["--verifySSL"].lower() == "true" else False
            args["--verifySSL"] = verify
        # get the Stash Username
        user = args["--user"]

        if not user and not args["--noReview"] and not args["--printSteps"]:
            args["--user"] = utility.getUserName(service="Stash")
            
        
        if args["--tickVersion"] is not False and args["--tickVersion"] is not True:
            if args["--tickVersion"].lower() == "false":
                args["--tickVersion"] = False
            else:
                args["--tickVersion"] = True

    def abort(self, args):
        #undo any commits done since we first started
        super(Publish, self)._resume(args)
        branch = git.currentBranch()
        utility.printMsg("Reverting all commits from %s from %s to %s" % (branch, self.progress["startingSHA"],
                                                                          git.SHA(branch)))
        revert = utility.userInput("This will apply to %s. continue? [y,n]" % git.currentBranch(), "y")
        if revert:
            git.revert("--no-edit %s..%s" % (self.progress["startingSHA"], "HEAD"))
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
        order = ["testForCleanWorkspace1", "verifyPublishActions", "md", "ensureReview", "verifyCompletedReview", 
                 "markInProgress", "tickVersion", "updateLog",
                 "build", "test", "testForCleanWorkspace2", "prePublish", "publish", "postPublish",
                 "tagVersion", "performCascades", "markAsDone", "notify", "deleteTopic", "done"]

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
                 "performCascades": self.performCascades,
                 "publish": self.publishAllProjects,
                 "postPublish": self.performCustomPostPublishSteps,
                 "deleteTopic": self.deleteTopicBranch,
                 "verifyCompletedReview": self.verifyCompletedReview,
                 "testForCleanWorkspace1": self.testForCleanWorkspace,
                 "testForCleanWorkspace2": self.testForCleanWorkspace,
                 "markInProgress": self.acquireInProgressLock,
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
                print(traceback.format_exc())
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
            utility.printMsg("Skipping In Progress Lock Check..")
            return True
        atlassian = Atlassian.Atlassian(username=args["--user"], url=args["--stashURL"], verify=args["--verifySSL"])
        repo = atlassian.project(args["--project"]).repo(args["--repo"])
        pullRequests = repo.pullRequests()
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
    def acquireInProgressLock(self, args):
        if args["--noReview"]:
            utility.printMsg("Skipping In Progress Lock Check..")
            return True
        retcode = self.checkInProgressLock(args)
        if retcode:
            # the 2 means we are already marked as in progress
            return ((retcode == 2) or self.markReviewAsInProgress(args)) and self.checkInProgressLock(args)
        else:
            return False

    def releaseInProgressLock(self, args):
        if args["--noReview"]:
            utility.printMsg("Skipping In Progress Lock Release...")
            return True

        atlassian = Atlassian.Atlassian(username=args["--user"], url=args["--stashURL"], verify=args["--verifySSL"])
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
        atlassian = Atlassian.Atlassian(username=args["--user"], url=args["--stashURL"], verify=args["--verifySSL"])
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
        ret = utility.isWorkspaceClean()
        ret = ret and grapeMenu.menu().applyMenuChoice("status", ["--failIfInconsistent"])
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

        # Commit any files that may have been added to the main repo.
        # The custom prepublish step is responsible for performing the git add for any
        # modified files.
        # Submodules and nested subprojects are not handled here.  If any files there are
        # modified during the prepublish step, the git add *and* the git commit must be
        # handled in the custom step.
        try:
            git.commit(" -m \"%s\"" % args["-m"])
        except git.GrapeGitError:
            pass

        return self.checkInProgressLock(args)

    def performCustomPostPublishSteps(self, args):
        return self.performCustomStep("postpublish", args)

    @staticmethod
    def getModifiedFileList(public, topic, args):
        # Limit the number of updated files displayed per subproject
        emailMaxFiles = args["--emailMaxFiles"]
        updatelist = git.diff("--name-only %s %s" % (public, topic)).split('\n')
        if len(updatelist) > emailMaxFiles:
            updatelist.append("[ Additional files not shown ]")
        return updatelist

    def loadModifiedFiles(self, args):
        if "modifiedFiles" in self.progress:
            return True
        wsdir = utility.workspaceDir()    
        os.chdir(wsdir)
        public = args["--public"]
        topic = args["--topic"]
        if git.SHA(public) == git.SHA(topic):
            public = utility.userInput("Please enter the branch name or SHA of the commit to diff against %s for the "
                                       "modified file list." % topic)

        self.progress["modifiedFiles"] = []

        # Get list of modified files in main repo
        self.progress["modifiedFiles"] += self.getModifiedFileList(public, topic, args)

        # Get list of modified files in submodules
        if args["--recurse"]:
            submodulePublic = args["--submodulePublic"]
            submodules = git.getModifiedSubmodules(public, topic)
            for sub in submodules:
               os.chdir(os.path.join(wsdir, sub))
               self.progress["modifiedFiles"] += [sub + "/" + s for s in self.getModifiedFileList(submodulePublic, topic, args)]
            os.chdir(wsdir)

        # Get list of modified files in nested subprojects
        for nested in grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes():
            os.chdir(os.path.join(wsdir, nested))
            self.progress["modifiedFiles"] += [nested + "/" + s for s in self.getModifiedFileList(public, topic, args)]
        os.chdir(wsdir)

        return True

    def loadVersion(self, args):
        if "version" in self.progress:
            return True
        else:
            menu = grapeMenu.menu()
            menu.applyMenuChoice("version", ["read"])
            guess = menu.getOption("version").ver
            self.progress["version"] = utility.userInput("Please enter version string for this commit", guess)
        return True

    def loadCommitMessage(self, args):
        if "commitMsg" in self.progress:
            if not args["-m"]:
                args["-m"] = self.progress["commitMsg"]
            return True
        if args["--noUpdateLog"]:
            self.progress["commitMsg"] = "no details entered"
            return True

        if not args["<CommitMessageFile>"] and not args["-m"]:
            proceed = utility.userInput("No commit message entered. Would you like to use the Pull Request's "
                                        "description as your  commit message? [y/n] \n(Enter 'n' to enter a file name with your commit message instead)", 'y')
            if not proceed:
                args["<CommitMessageFile>"] = utility.userInput("Enter the name of the file containing your commit "
                                                                "message: ")

        if args["<CommitMessageFile>"] and not args["-m"]:
            # commit message should come from the file
            commitMsgFile = args["<CommitMessageFile>"]
            try:
                with open(commitMsgFile, 'r') as f:
                    commitMsg = f.readlines()+["\n"]

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
        elif args["-m"]: 
            commitMsg = [args["-m"]+"\n"] 
        else:
            if args["--noReview"]:
                utility.printMsg("Skipping retrieval of commit message from Pull Request description..")
                if not args["-m"]:
                    print("File with commit message is required argument when publishing with --noReview and no -m "
                          "<msg> defined.")
                    return False
            utility.printMsg("Retrieving pull request description for use as commit message...")
            atlassian = Atlassian.Atlassian(username=args["--user"], url=args["--stashURL"], verify=args["--verifySSL"])
            repo = atlassian.project(args["--project"]).repo(args["--repo"])
            pullRequest = repo.getOpenPullRequest(args["--topic"], args["--public"])
            commitMsg = pullRequest.description().splitlines(True)+['\n']

        # this will be used for the actual merge commit message.
        escapedCommitMsg = ''.join(commitMsg).replace("\"", "\\\"")
        escapedCommitMsg = escapedCommitMsg.replace("`", "'")
        
        if escapedCommitMsg: 
            args["-m"] = escapedCommitMsg
        else:
            utility.printMsg("WARNING: Commit message is empty. ")

        utility.printMsg("The following commit message will be used for email notification, merge commits, etc.\n"
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
            args["-m"] = escapedCommitMsg
            return True

    def updateLog(self, args):
        if not (self.loadCommitMessage(args) and self.loadVersion(args)):
            return False
        commitMsg = self.progress["commitMsg"].split('\n')

        if args["--noUpdateLog"]:
            return True
        logFile = args["--updateLog"]
        cwd = os.getcwd()
        os.chdir(utility.workspaceDir())
        if logFile:
            header = args["--entryHeader"]
            header = header.replace("<date>", time.asctime())
            header = header.replace("<user>", git.config("--get user.name"))
            header = header.replace("<version>", self.progress["version"])
            header = ["\n"]+header.split("\\n")
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
        if not args["--tickVersion"]:
            return True
        menu = grapeMenu.menu()
        if not args["--noReview"]:
            atlassian = Atlassian.Atlassian(username=args["--user"], url=args["--stashURL"], verify=args["--verifySSL"])
            repo = atlassian.project(args["--project"]).repo(args["--repo"])
            thisRequest = repo.getOpenPullRequest(args["--topic"], args["--public"])
            requestTitle = thisRequest.title()
            versionArgs = ["read"]
            menu.applyMenuChoice("version", versionArgs)
            currentVer = grapeMenu.menu().getOption("version").ver
            if currentVer in requestTitle:
                utility.printMsg("Current Version string already in pull request title. Assuming this is from "
                "a previous call to grape publish. Not ticking version again.")
                return True
        ret = True
        if args["--tickVersion"]:
            versionArgs = ["tick", "--notag", "--public=%s" % args["--public"]]
            for arg in args["-T"]:
                versionArgs += [arg.strip()]
            ret = grapeMenu.menu().applyMenuChoice("version", versionArgs)
            self.progress["version"] = grapeMenu.menu().getOption("version").ver
            ret = ret and self.markReviewWithVersionNumber(args)
        return ret and self.checkInProgressLock(args)

    @staticmethod
    def tagVersion(args):
        ret = True
        if args["--tickVersion"]:
            versionArgs = ["tick", "--tag", "--notick", "--nocommit", "--tagNested"]
            for arg in args["-T"]:
                versionArgs += [arg.strip()]
            cwd = os.getcwd()
            wsdir = utility.workspaceDir()    
            os.chdir(wsdir)
            ret = grapeMenu.menu().applyMenuChoice("version", versionArgs)
            for nested in grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes():
               os.chdir(os.path.join(wsdir, nested))
               git.push("--tags origin")
            os.chdir(wsdir)
            git.push("--tags origin")
            os.chdir(cwd)
        return ret

    def sendNotificationEmail(self, args):

        if not (self.loadCommitMessage(args) and self.loadVersion(args) and self.loadModifiedFiles(args)):
            return False
        # Write the contents of the mail file out to a temporary file
        mailfile = tempfile.mktemp()

        with open(mailfile, 'w') as mf:
           date = time.asctime()
           emailHeader = args["--emailHeader"]
           emailHeader = emailHeader.replace("<user>", git.config("--get user.name"))
           emailHeader = emailHeader.replace("<date>", date)
           emailHeader = emailHeader.replace("<version>", self.progress["version"])
           emailHeader = emailHeader.replace("<public>", args["--public"])
           emailHeader = emailHeader.split("\\n")
           mf.write('\n'.join(emailHeader))
           comments = self.progress["commitMsg"]
           mf.write('\n')
           mf.write(comments)
           updatelist = self.progress["modifiedFiles"]
           if len(updatelist) > 0:
               mf.write("\nFILES UPDATED:\n")
               mf.write("\n".join(updatelist))

        if not args["--emailNotification"].lower() == "true":
            utility.printMsg("Skipping E-mail notification..")
            with open(mailfile, 'r') as mf:
               utility.printMsg("-- Begin update message --")
               utility.printMsg(mf.read())
               utility.printMsg("-- End update message --")
            return True

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
        tolist = msg['To'].split(',')
        tolist.append(myemail)
        s.sendmail(msg['From'], tolist, msg.as_string())
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
            print args["-m"]
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
        

    @staticmethod
    def rebase(public, topic):
        print("rebasing %s onto %s" % (topic, public))
        git.rebase(public)
        print("%s successfully rebased onto %s" % (topic, public))
        git.checkout(public)
        git.merge(topic)
        print("You are currently on %s" % public)
        
    def parseConfigPublishPolicy(self, args, policy, defaultCascadeDestination, repoType="outer"):
        # if the policy starts with cascade, we allow a cascade->Branch->branch2->... syntax in the config file
        policyToks = policy.strip().lower().split('->')
        if policyToks[0] == "cascade":
            policy = "squash"
            # restore cascade info from an abort if necessary
            if "<<cascadeDict>>" in args and args["<<cascadeDict>>"] is not None:
                self.cascadeDict = args["<<cascadeDict>>"]
                args["<<cascadeDict>>"] = None    
            if len(policyToks) > 1:
                self.cascadeDict[repoType] = policyToks[1:]
            else:
                self.cascadeDict[repoType] = [defaultCascadeDestination]
        args["<<cascadeDict>>"] = self.cascadeDict
        return policy
    
    def parseCascadeArgs(self, args): 
        if args["--cascade"]:
            self.cascadeDict["outer"] = args["--cascade"]
            args["<<cascadeDict>>"] = self.cascadeDict

    def performCascades(self, args):
        self.loadPublishTargets(args)
        
        if "<<cascadeDict>>" in args and args["<<cascadeDict>>"]:
            self.cascadeDict = args["<<cascadeDict>>"]
         
        wsdir = utility.workspaceDir()    
        if self.cascadeDict:
            # do outer level and nested project cascades
            cascade = self.cascadeDict["outer"]
            repos= [""]+grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes()
            repos = [os.path.join(wsdir,r) for r in repos]
            for repo in repos:
                public = args["--public"]
                os.chdir(repo)
                for branch in cascade:
                    git.checkout(branch)
                    git.merge("%s -m \"GRAPE PUBLISH: cascade merge of %s to %s after publish.\"" % (public, public, branch))
                    public = branch 
                    git.push("origin %s" % branch)
                    
            if "submodules" in self.cascadeDict and "<<publishedSubmodules>>" in args:
                cascade = self.cascadeDict["submodules"]
                repos = [os.path.join(wsdir,r) for r in args["<<publishedSubmodules>>"]]
                for repo in repos:
                    os.chdir(repo)
                    public = args["--submodulePublic"]
                    for branch in cascade:
                        git.checkout(branch)
                        git.merge("%s -m \"GRAPE PUBLISH: cascade merge of %s to %s after publish.\"" % (public, public, branch))
                        public = branch 
                        git.push("origin %s" % branch)
            os.chdir(wsdir)
            
        return True
                 
                

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
        recurse = config.get('workspace', 'manageSubmodules')
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
            self.modifiedSubtrees = self.modifiedSubtrees.union(set(args["--forcePushSubtree"]))
            for st in allsubtrees:
                prefix = config.get('subtree-%s' % st, 'prefix')
                if git.diff("--name-only %s %s -- %s" % (public, topic, prefix), quiet=quiet):
                    self.modifiedSubtrees.append(st)
            for st in self.modifiedSubtrees:
                self.st_prefixes[st] = config.get('subtree-%s' % st, 'prefix')
                self.st_remotes[st] = utility.parseSubprojectRemoteURL(config.get('subtree-%s' % st, 'remote'))
                self.st_branches[st] = config.getMapping('subtree-%s' % st, 'topicPrefixMappings')[topic]
        
        # deal with nested subprojects
        self.modifiedNestedProjects =  grapeConfig.GrapeConfigParser.getAllModifiedNestedSubprojectPrefixes(public,topic)
                                                                                                           
        
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
        
        userMsg = "When ready, grape will publish %s to:\n" % topic
        
        useAnd = False
        if recurse:
            userMsg += "%s for the following submodules:\n\t\t%s\n" % (args["--submodulePublic"], "\n\t\t".join(submodules))
            useAnd = True
            
        if self.modifiedNestedProjects: 
            prefixes = self.modifiedNestedProjects 
            userMsg += "%s for the following nested subprojects:\n\t\t%s\n" % (public, "\n\t\t".join(prefixes))
            useAnd = True
        
        userMsg += "%s%s for the outer level repo. \nProceed? [y/n]" % ("and " if useAnd else "", public)
        
        proceed = utility.userInput(userMsg, 'y')
        if not proceed:
            return False

        push_subtrees = args["--pushSubtrees"]
        if push_subtrees:
            if self.modifiedSubtrees:
                utility.printMsg("When ready, grape will publish the following subtrees to the following destinations:")
                for st in self.modifiedSubtrees:
                    print("subtree: %s\trepo: %s\tbranch:%s" % (self.st_prefixes[st], self.st_remotes[st],
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

        # remember this since Command Line defined policies override the submodule policies as well.
        CLPolicy = policy

        # update policy from config if not set on CL
        if not policy:
            policy = self.parseConfigPublishPolicy(args, config.getMapping('flow', 'publishPolicy')[public], topic)
        
        self.parseCascadeArgs(args)
            
        wsdir = utility.workspaceDir()    
        os.chdir(wsdir)

        if recurse:
            submodulePublic = args["--submodulePublic"]
            submodules = git.getModifiedSubmodules(public, topic)
            # submodule policy is Command Line requested policy, otherwise is based on 
            #       .grapeconfig.workspace.submodulePublishPolicy
            submodulePolicy = CLPolicy
            # store current value for args["--cascade"]
            outerCascadeOption = args["--cascade"]
            if not submodulePolicy:
                submodulePolicy = config.getMapping('workspace', 'submodulePublishPolicy')[submodulePublic]
                submodulePolicy = self.parseConfigPublishPolicy(args, submodulePolicy, topic, repoType="submodule")

            valid = self.validateInput(submodulePolicy, args)
            if valid and self.verifyPublishTargetsWithUser(args):
                for sub in submodules:
                    os.chdir(os.path.join(wsdir, sub))

                    grapeMenu.menu().applyMenuChoice('up', ['up', '--public=%s' % submodulePublic])
                    self.publish(submodulePolicy, submodulePublic, topic, args)
                    os.chdir(wsdir)
                    #add and commit any new merge commits in submodules as a result of the publish
                    git.add(sub)
                try:
                    # we are cool with this not working - only will have something to commit if the 
                    # submodules were published without fast forward merges
                    git.commit("-m \"%s - submodules published\"" % args["-m"])
                except git.GrapeGitError:
                    pass
            

            # restore value for args["--cascade"]
            args["<<publishedSubmodules>>"] = submodules
            args["--cascade"] = outerCascadeOption
            os.chdir(wsdir)


        # push subtrees to their respective remote branches
        push_subtrees = args["--pushSubtrees"]
        if push_subtrees:
            modifiedSubtrees = self.modifiedSubtrees
            if modifiedSubtrees: 
                proceed = self.verifyPublishTargetsWithUser(args)
                if proceed:
                    squash = "--squash" if config.get("subtrees", "mergepolicy").lower() == "squash" else ""
                    for st in modifiedSubtrees:
                        print("pushing subtree %s to %s (branch %s)..." % (self.st_prefixes[st],
                                                                              self.st_remotes[st], self.st_branches[st]))

                        try:
                            git.subtree("push --prefix=%s %s %s " % (self.st_prefixes[st],
                                                                                 self.st_remotes[st],  self.st_branches[st]),
                                                                                 quiet=quiet)
                        except git.GrapeGitError:
                            # the push can fail if there has never been a subtree add / pull in this repo.
                            utility.printMsg("First attempt failed. Attempting a subtree pull then push...")
                            git.subtree("pull %s --prefix=%s %s %s " % (squash, self.st_prefixes[st],
                                                                                 self.st_remotes[st], self.st_branches[st]), quiet=quiet)
                            git.subtree("push --prefix=%s %s %s " % ( self.st_prefixes[st],
                                                                                 self.st_remotes[st], self.st_branches[st]), quiet=quiet)
                            utility.printMsg("Succeeded!")



        valid = self.validateInput(policy, args)
        if valid and self.verifyPublishTargetsWithUser(args):
            for nested in grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes():
                os.chdir(os.path.join(wsdir,  nested))
                self.publish(policy, public, topic, args)
            os.chdir(wsdir)
            self.publish(policy, public, topic, args)
            return True
        else:
            return False
