import io
import json
import logging
import os
import re
import smtplib
import socket
import tempfile
import time
import traceback
try:
    from email.mime.text import MIMEText
except ImportError:
    from email.MIMEText import MIMEText
from vine import CodeReviewsFactory
from vine import config_parser_global
from vine import config_parser_user
from vine import grape_errors
from vine import grapeGit as git
from vine import grapeMenu
from vine import utility
from vine import vine_subprocess
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.option import Option
from vine.resumable import Resumable
from vine.vine_logging import log_wrapper
import stashy.stashy.errors as stashyErrors


class PublishStepFailed(Exception):
    def __init__(self, stepName):
        assert isinstance(stepName, str)
        self.stepName = stepName


class Publish(Resumable, Option, WorkspaceDirHandler):
    """
    grape publish
    Merges/Squash-merges/Rebases the current topic branch <type>/<username>/<descr> into the public <branch>,
    where <public> is read from one of the <type>:<public> pairs found in .grapeconfig.flow.topicPrefixMappings,
    .grapeconfig.flow.topicDestinationMappings, and/or .grapeconfig.workspace.submoduleTopicPrefixMappings. The
    branch-dependent publish policy (merge vs. squash merge. vs rebase, etc) is decided using
    grapeconfig.flow.publishPolicy for the top-level repo and the publish policy for
    submodules is decided using grapeconfig.workspace.submodulePublishPolicy.

    Usage:  grape-publish [--squash [--cascade=<branch>... ] | --merge |  --rebase]
                         [--mergeTrain=<bool>]
                         [-m <msg>]
                         [--recurse | --noRecurse]
                         [--public=<public> [--submodulePublic=<submodulePublic>]]
                         [--topic=<branch>]
                         [--noverify]
                         [--nopush]
                         [--pushSubtrees | --noPushSubtrees]
                         [--forcePushSubtree=<subtreeName>]...
                         [--startAt=<startStep>] [--stopAt=<stopStep>]
                         [--buildCmds=<buildStr>] [--buildDir=<path>]
                         [--testCmds=<testStr>] [--testDir=<path>]
                         [--testCIJob=<jobStr>]
                         [--prepublishCmds=<cmds>] [--prepublishDir=<path>]
                         [--postpublishCmds=<cmds>] [--postpublishDir=<path>]
                         [--noUpdateLog | [[--updateLogDir=<dir>] --updateLog=<file> --skipFirstLines=<int> --entryHeader=<string>]]
                         [--tickVersion=<bool> [-T <arg>]...]
                         [--tickOnCascade=<slot> ]
                         [--user=<BitbucketUserName>]
                         [--codeReviewsURL=<httpsURL>]
                         [--verifySSL=<bool>]
                         [--project=<BitbucketProjectKey>]
                         [--repo=<BitbucketRepoName>]
                         [-R <arg>]...
                         [--noReview]
                         [--useBitbucket=<bool>]
                         [--deleteTopic=<bool>]
                         [--emailNotification=<bool> [--emailHeader=<str> --emailFooter=<str>
                          --emailSubject=<str> --emailSendTo=<addr> --emailServer=<smtpserver> --emailMaxFiles=<int>]]
                         [<CommitMessageFile>]
                         [--remoteMerge]
                         [--quiet]
                         [--ssh_pat_url=<url>]
                         [--ssh_pat_port=<int>]
            grape-publish --continue
            grape-publish --abort
            grape-publish --printSteps
            grape-publish --quick -m <msg> [--user=<BitbucketUserName>] [--public=<public>] [--noReview] [--remoteMerge] [--ssh_pat_url=<url>] [--ssh_pat_port=<int>]
            grape-publish  --mergeUpdateLogs --mergedLog=<file> --startVersion=<ver> [--stopVersion=<ver>] [--updateLogDir=<dir>] [--tagPrefix=<str>] [--tagSuffix=<str>] [--updateLog=<file>]
            grape-publish --sendEmail [--emailNotification=<bool> [--emailHeader=<str> --emailFooter=<str> --emailSubject=<str> --emailSendTo=<addr>
                                     --emailServer=<smtpserver> --emailMaxFiles=<int>]] --topic=<branch>

    Options:
    --squash                Squash merges the topic into the public, then performs a commit if the merge goes clean.
    --cascade=<branch>      For squash merges, can choose to cascade back to <branch> after the merge is
                            completed. Define multiple times to setup a chain of cascades. Overrides outer repo and
                            nestedSubproject cascades defined in .grapeconfig publish policies. Does not override
                            submodule publish policies.
    --merge                 Perform a normal merge.
    --mergeTrain=<bool>     Use the Merge Train feature supported by Gitlab - GRAPE will push an update and then ask Gitlab to enqueue the update
                            in an active merge train.
                            [default: .grapeconfig.publish.mergeTrain]
    -m <msg>                The commit message to use for a successful merge / squash merge. Ignored if used with
                            --rebase.
    --rebase                Rebases the topic branch to the public, then fast forwards the public to the tip of the
                            topic.
    --recurse               Perform the publish action in submodules.
                            Defaults to True if .grapeconfig.workspace.manageSubmodules is True.
    --noRecurse             Do not perform the publish action in submodules.
                            Defaults to True if .grapeconfig.workspace.manageSubmodules is False.
    --topic=<branch>        The branch to publish. Defaults to the current branch.
    --noverify              Set to skip interactive verification of publish commands.
    --nopush                Set to skip the push of commits generated during the publish procedure.
    --pushSubtrees          Push subtrees to their respective remotes (.grapeconfig.subtree-<name>.remote) appropriate
                            public branches (.grapeconfig.subtree-<name>.topicPrefixMappings)
                            Set by default if .grapeconfig.subtrees.pushOnPublish is True.
    --noPushSubtrees        Don't perform a git subtree push.
    --startAt=<startStep>   The publish step to start at. One of "testForCleanWorkspace1", "md1",
                            "ensureModifiedSubmodulesAreActive", "verifyPublishActions", "ensureReview",
                            "verifyCompletedReview", "markInProgress", "md2", "tickVersion", "updateLog",
                            "build", "test", "testForCleanWorkspace2", "prePublish", "publish", "postPublish",
                            "tagVersion", "performCascades", "markAsDone", "notify", or "deleteTopic".
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
    --testCIJob=<jobStr>    The comma-delimited list of required passing CI jobs that allows short circuiting of
                            testing during publish. 
                            [default: .grapeconfig.publish.testCIJob]
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
    --deleteTopic=<bool>    Offer to delete the topic branch when done. [default: .grapeconfig.publish.deleteTopic]
    --noUpdateLog           Set to skip the updateLog step.
    --updateLogDir=<dir>    Directory to put update log messages. Can use <major_version> and/or <minor_version> to have
                            a directory named after current development version.
                            [default: .grapeconfig.publish.updateLogDir]
    --updateLog=<file>      The log file to update with the commit message for this branch. If --updateLogDir is defined,
                            this is the base file name for update message files.
                            [default: .grapeconfig.publish.updateLog]
    --skipFirstLines=<int>  The number of lines to skip in the updateLog file before inserting the commit message.
                            [default: .grapeconfig.publish.logSkipFirstLines]
    --entryHeader=<string>  The format for the commit message header. The string literals <date>, <user>, and <version>
                            will be replaced by the date, the result of git config --get user.name, and the result of
                            git describe --abbrev=0 after the tickversion step, respectively.
                            [default: .grapeconfig.publish.logEntryHeader]
    --tickVersion=<bool>    Tick a version number as a part of this publish action.
                            [default: .grapeconfig.publish.tickVersion]
    --tickOnCascade=<slot>  Tick the <slot> version number when performing a cascade.
                            Default behavior governed by the flow.topicCascadeTick mapping.
    -T <arg>                An argument to pass to grape-version tick. Type grape version --help for available options
                            and defaults. -T can be used multiple times to pass multiple arguments.
    --user=<user>           Your Bitbucket/Gitlab username.
    --codeReviewsURL=<url>  Your Bitbucket/Gitlab URL, e.g. https://your.home.org/bitbucket .
                            [default: .grapeconfig.project.codeReviewsURL]
    --verifySSL=<bool>      Set to False to ignore SSL certificate verification issues.
                            [default: .grapeconfig.project.verifySSL]
    --project=<project>     Your Bitbucket Project. See grape-review for more details.
                            [default: .grapeconfig.project.name]
    --repo=<repo>           Your Bitbucket repo. See grape-review for more details.
                            [default: .grapeconfig.repo.name]
    -R <arg>                Argument(s) to pass to grape-review, in addition to --title="**IN PROGRESS**:" --prepend.
                            Type grape review --help for valid options.
    --noReview              Don't perform any actions that interact with pull requests. Overrides --useBitbucket.
    --useBitbucket=<bool>   Whether or not to use pull requests. [default: .grapeconfig.publish.useStash]
    --public=<public>       The branch to publish to. Defaults to the mapping for the current topic branch as described
                            by .grapeconfig.flow.topicDestinationMappings. .grapeconfig.flow.topicPrefixMappings is used
                            if no option for .grapeconfig.flow.topicDestinationMappings exists.
    --submodulePublic=<b>   The branch to publish to in submodules. Defaults to the mapping for the current topic branch
                            as described by .grapeconfig.workspace.submoduleTopicPrefixMappings.
    --emailNotification=<b> Set to true to send a notification email after you've published. The email will consist of
                            a header <header> and a message, generally the contents of <CommitMessageFile> and/or
                            the Pull Request description, followed by a footer <footer>. The email is sent to <addr>,
                            and will be CC'd to the user.
                            For the email subject, header and footer, the string literals
                            '<user>', '<date>', '<version>', and '<public>' with the following:
                            <user>: the result of git config --get user.name
                            <date>: the current timestamp.
                            <version>: The version of the project, so long as grape is managing your versioning.
                            <public>: The branch to publish to.
                            [default: .grapeconfig.publish.emailNotification]
    --emailHeader=<header>  The email header. See above.
                            [default: .grapeconfig.publish.emailHeader]
    --emailFooter=<footer>  The email footer. See above.
                            [default: .grapeconfig.publish.emailFooter]
    --emailSubject=<sbj>    The email subject. See above.
                            [default: .grapeconfig.publish.emailSubject]
    --emailSendTo=<addr>    The comma-delimited list of receivers of the email.
                            [default: .grapeconfig.publish.emailSendTo]
    --emailServer=<server>  The smtp email server address.
                            [default: .grapeconfig.publish.emailServer]
    --emailMaxFiles=<int>   Maximum number of modified files (per subproject) to show in email.
                            [default: .grapeconfig.publish.emailMaxFiles]
    --quick                 Perform the following steps only: md1, ensureModifiedSubmodulesAreActive, ensureReview,
                            markInProgress, md2, publish, markAsDone, deleteTopic, done]
    --remoteMerge           Perform the merge using the Bitbucket REST API.
    --quiet                 Suppress output from custom build and test steps unless there is a failure.
    --ssh_pat_url=<url>     SSH URL for generating Personal Access Tokens to authenticate into a Code Review service's
                            REST API.
                            [default: .grapeconfig.repo.ssh_pat_url]
    --ssh_pat_port=<int>    Port number to issue ssh command over to generate a Personal Access Token for authentication
                            into a Code Review service's REST API.
                            [default: .grapeconfig.repo.ssh_pat_port]
    --mergeUpdateLogs       If you are using a merge train workflow, this command can be used to produce a file that
                            is a concatenation of merge request update log files, with the merge request version
                            substituted out for appropriate version tags.
    --mergedLog=<file>      The file to write the merged update logs to.
    --startVersion=<ver>    Starting version to search for relevant update message files.
    --stopVersion=<ver>     Most recent version to search for relevant update message files. Defaults to HEAD.
    --tagPrefix=<str>       The prefix for the git version tags. [default: v]
    --tagSuffix=<str>       The suffix for the git version tags. Default value comes from
                            .grapeconfig.versioning.branchTagSuffixMappings.


    Optional Arguments:
    <CommitMessageFile>     A file with an update message for this publish command. The pull request associated with
                            this branch will be updated to contain this message. If you don't specify a filename, grape
                            will give you an opportunity to use contents of the pull request description are intended for the update
                            message. Both the commit message for the merge and an update log will contain this message.
                            Additionally, if email notification is configured, the contents of the email will have
                            this message.



    """

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
        self.doDelete = {}
        self._codeReviews = None
        self._repo = None

    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_WORKSPACE)
        config.ensureSection(self.SECTION_FLOW)
        config.ensureSection(self.SECTION_SUBTREES)
        config.ensureSection(self.SECTION_PUBLISH)

        # workspace defaults
        config.set(self.SECTION_WORKSPACE, 'manageSubmodules', 'True')
        config.set(self.SECTION_WORKSPACE, 'submoduleTopicPrefixMappings', '?:develop')
        config.set(self.SECTION_WORKSPACE, 'submodulePublishPolicy', '?:merge')
        # publish policy defaults
        config.set(self.SECTION_FLOW, 'publishPolicy', '?:merge')
        config.set(self.SECTION_PUBLISH, 'mergeTrain', 'False')
        # subtree publish actions
        config.set(self.SECTION_SUBTREES, 'names', '')
        config.set(self.SECTION_SUBTREES, 'pushOnPublish', "False")
        # build steps
        config.set(self.SECTION_PUBLISH, 'buildCmds', '')
        config.set(self.SECTION_PUBLISH, 'buildDir', '.')
        # test steps
        config.set(self.SECTION_PUBLISH, 'testCmds', '')
        config.set(self.SECTION_PUBLISH, 'testDir', '.')
        config.set(self.SECTION_PUBLISH, 'testCIJob', '')
        # prepublish steps
        config.set(self.SECTION_PUBLISH, 'prepublishCmds', '')
        config.set(self.SECTION_PUBLISH, 'prepublishDir', '.')
        # postpublish steps
        config.set(self.SECTION_PUBLISH, 'postpublishCmds', '')
        config.set(self.SECTION_PUBLISH, 'postpublishDir', '.')
        # tick the version?
        config.set(self.SECTION_PUBLISH, 'tickVersion', 'False')
        # use Bitbucket for checking Pull Request status?
        config.set(self.SECTION_PUBLISH, 'useStash', 'True')
        # delete when done
        config.set(self.SECTION_PUBLISH, 'deleteTopic', 'False')
        # log file
        config.set(self.SECTION_PUBLISH, 'updateLog', '.grapepublishlog')
        config.set(self.SECTION_PUBLISH, 'updateLogDir', '')
        config.set(self.SECTION_PUBLISH, 'logSkipFirstLines', '0')
        config.set(self.SECTION_PUBLISH, 'logEntryHeader', "<date> <user>\\n<version>\\n")
        # email config
        config.set(self.SECTION_PUBLISH, 'emailNotification', 'False')
        config.set(self.SECTION_PUBLISH, 'emailHeader', '<public> updated to <version>')
        config.set(self.SECTION_PUBLISH, 'emailFooter', '')
        config.set(self.SECTION_PUBLISH, 'emailServer', 'smtp.email.server')
        config.set(self.SECTION_PUBLISH, 'emailSendTo', 'user.list@company.com')
        config.set(self.SECTION_PUBLISH, 'emailSubject', '<public> updated to <version>')
        config.set(self.SECTION_PUBLISH, 'emailMaxFiles', '100')
        # tick on cascade behavior
        config.set(self.SECTION_FLOW, "topicCascadeTick","?:0")

    def description(self):
        try:
            current = git.currentBranch(execution_path=self.workspace_dir)
            public = config_parser_global.grapeConfig().getPublicBranchFor(
                git.currentBranch(execution_path=self.workspace_dir))
        except grape_errors.GrapeGitError:
            public = "Unknown"
            current = "Unknown"
        except KeyError:
            public = "Unknown"
            current = "Unknown"
        return f"Publish the current {git.branchPrefix(current)} " + \
               f"branch to {public}"

    def _resume(self, args, *, workspace_dir):
        super(Publish, self)._resume(args, workspace_dir=workspace_dir)
        self.execute(args)

    def _saveProgress(self, args):
        pass

    def parseArgs(self, args):
        # resolve default topic branch, ensure we are on the topic branch
        topic = args["--topic"]
        if not topic:
            topic = git.currentBranch(execution_path=self.workspace_dir)
        if topic != git.currentBranch(execution_path=self.workspace_dir) and \
                args['--startAt'] and self.order in args['--startAt'] and \
                'publish' in args["--startAt"]:
            git.checkout(topic, execution_path=self.workspace_dir)
        args["--topic"] = topic

        # resolve default public branch using .grapeconfig.flow.topicPrefixMappings
        config = config_parser_global.grapeConfig()
        prefix = git.branchPrefix(topic)
        public = args["--public"]
        if not public:
            public = config.getPublicBranchFor(topic)
        args["--public"] = public
        self.branchPrefix = prefix
        # whether or not to use Bitbucket
        if args["--useBitbucket"].lower() == "false" and not args["--noReview"]:
            args["--noReview"] = True
        if not args["--noReview"] and not isinstance(args["--verifySSL"], bool):
            verify = args["--verifySSL"].lower() == "true"
            args["--verifySSL"] = verify
        # get the Bitbucket Username
        user = args["--user"]

        if not user and not args["--noReview"] and not args["--printSteps"]:
            args["--user"] = utility.getUserName(service="Bitbucket")


        if args["--tickVersion"] is not False and args["--tickVersion"] is not True:
            if args["--tickVersion"].lower() == "false":
                args["--tickVersion"] = False
            else:
                args["--tickVersion"] = True
        if  args["--tickOnCascade"] is None:
            args["--tickOnCascade"] = int(config.getMapping(self.SECTION_FLOW, "topicCascadeTick")[args["--topic"]])

        #whether mergeTrains are enabled
        if args["--mergeTrain"]:
            if args["--mergeTrain"] is not True and args["--mergeTrain"] is not False:
                doMergeTrain = args["--mergeTrain"].lower() == "true"
                args["--mergeTrain"] = doMergeTrain
        
        # store the args in self
        self.args = args


    def abort(self, args):
        #undo any commits done since we first started
        super(Publish, self)._resume(args, workspace_dir=self.workspace_dir)
        branch = git.currentBranch(execution_path=self.workspace_dir)
        if self.progress["startingSHA"] != git.SHA(branch, execution_path=self.workspace_dir):
            logging.info(f"Reverting all commits from {branch} from " +
                         f"{self.progress['startingSHA']} to {git.SHA(branch, execution_path=self.workspace_dir)}")
            revert = utility.userInput(
                f"This will apply to {branch}. continue? [y,n]", "y")
            if revert:
                git.revert(f"--no-edit {self.progress['startingSHA']}..HEAD",
                           execution_path=self.workspace_dir)
        # release IN PROGRESS LOCK
        logging.info("Releasing In Progress Lock")
        self.releaseInProgressLock(args)

    @log_wrapper
    def execute(self, args):
        self.set_progress_file(execution_path=self.workspace_dir)

        # this is needed for all custom actions, ensure it is initialized for all cases here
        self.progress["CIPassed"] = False

        if args["--abort"]:
            self.abort(args)
            return True
        if "startingSHA" not in self.progress:
            self.progress["startingSHA"] = git.SHA("HEAD",
                                                   execution_path=self.workspace_dir)

        self.parseArgs(args)

        if args["--mergeUpdateLogs"]:
            self.mergeUpdateLogs(args)
            return True

        if args["--quick"]:
            self.order = ["md1","ensureModifiedSubmodulesAreActive","ensureReview", "verifyPublishActions", "markInProgress", "md2", "publish",
                          "markAsDone", "deleteTopic", "done"]
        elif args["--sendEmail"]:
            self.order = ["notify", "done"]
        elif args["--mergeTrain"]:
            # steps for queuing in the merge train
            self.order = ["testForCleanWorkspace1", "ensureModifiedSubmodulesAreActive",
                          "verifyPublishActions", "ensureReview", "verifyCompletedReview", "markInProgress",
                          "checkCI", "build", "test",
                          "testForCleanWorkspace2", "updateLog", "prePublish", "tagVersion", "push", "requestUserStartMergeTrain", "done"]
        else:
            self.order = ["testForCleanWorkspace1", "md1", "ensureModifiedSubmodulesAreActive",
                          "verifyPublishActions", "ensureReview", "verifyCompletedReview",
                          "markInProgress", "md2", "checkCI", "tickVersion", "updateLog",
                          "build", "test", "testForCleanWorkspace2", "prePublish", "publish", "postPublish",
                          "tagVersion", "performCascades", "markAsDone", "notify", "deleteTopic", "done"]

        startPoint = args["--startAt"]

        if args["--printSteps"]:
            logging.info(self.order)
            return True

        if startPoint:
            if startPoint not in self.order:
                logging.info(f"{startPoint} not a valid publish step. " +
                             f"Choose 1 of :\n{self.order}")
                return False
        else:
            startPoint = self.order[0]

        stopPoint = args["--stopAt"]

        if stopPoint:
            if stopPoint not in self.order:
                logging.info(
                    f"{stopPoint} not a valid publish step." +
                    f"Choose 1 of :\n{self.order}")
                return False

        steps = {"checkCI": self.performCICheck,
                 "build": self.performCustomBuildStep,
                 "test": self.performCustomTestStep,
                 "prePublish": self.performCustomPrePublishSteps,
                 "tickVersion": self.tickVersion,
                 "tagVersion": self.tagVersion,
                 "performCascades": self.performCascades,
                 "publish": self.publishAllProjects,
                 "push": self.push,
                 "postPublish": self.performCustomPostPublishSteps,
                 "deleteTopic": self.deleteTopicBranch,
                 "verifyCompletedReview": self.verifyCompletedReview,
                 "testForCleanWorkspace1": self.testForCleanWorkspace,
                 "testForCleanWorkspace2": self.testForCleanWorkspace,
                 "markInProgress": self.acquireInProgressLock,
                 "markAsDone": self.releaseInProgressLock,
                 "mergeOnSuccess" : self.mergeOnSuccess,
                 "updateLog": self.updateLog,
                 "notify": self.sendNotificationEmail,
                 "ensureReview": self.ensureReview,
                 "ensureModifiedSubmodulesAreActive": self.ensureModifiedSubmodulesAreActive,
                 "md1": self.mergePublic,
                 "md2": self.mergePublic,
                 "requestUserStartMergeTrain": self.requestUserStartMergeTrain,
                 "verifyPublishActions": self.verifyPublishTargetsWithUser}


        currentStep = startPoint
        for step in self.order:
            if step == "done":
                break
            if step == stopPoint:
                logging.info(f"Stopping at {stopPoint} step as requested.")
                args["--startAt"] = step
                self.dumpProgress(args)
                return True
            if step != currentStep:
                continue
            try:
                # Save the progress before attempting a step (this ensures that the progress
                # is saved even if the first step after a --continue fails).
                args['workspace_dir'] = self.workspace_dir
                self.dumpProgress(args)

                ret = steps[step](args)

                # Save the progress immediately after a successful step (in case there is an
                # uncaught interruption in between steps).
                self.dumpProgress(args)
            except BaseException as e:
                self.bailOut(step, args)
                logging.error(traceback.format_exc())
                return False
            if ret:
                currentStep = self.order[self.order.index(currentStep) + 1]
            else:
                self.bailOut(step, args)
                return False

        return True

    def bailOut(self, step, args):
        logging.info(
            f"Publish step {step.upper()} failed. Please resolve the issue" +
            " and then continue using\ngrape publish --continue")
        args["--startAt"] = step
        self.dumpProgress(args)
        return

    def ensureModifiedSubmodulesAreActive(self, args):
        missing = utility.getModifiedInactiveSubmodules(
            args["--public"], args["--topic"], includeAdded=True,
            workspace_dir=self.workspace_dir)
        if missing:
            logging.info("The following submodules that you've modified are not currently present in your workspace.\n"
                             "You should activate them using grape uv and then call publish --continue")
            logging.info(','.join(missing))
            return False
        return True

    def mergePublic(self, args):
        menu = grapeMenu.menu(workspace_dir=self.workspace_dir)
        if  menu.applyMenuChoice("md", ["--am", f"--public={args['--public']}"]):
            # update the startingSHA to be after any merges as they cause all sorts of problems for git revert in the
            # event of a grape publish --abort
            self.progress["startingSHA"] = git.SHA("HEAD", execution_path=self.workspace_dir)
            return True
        else:
            return False


    def markReview(self, args, newArgs, skipStr, updateOnly=True):
        if args["--noReview"]:
            logging.info(skipStr)
            return True
        reviewArgs = args["-R"]
        finalArgs = []
        if updateOnly:
            finalArgs = ["--update"]
        finalArgs += [f"--source={args['--topic']}",
                      f"--target={args['--public']}",
                      f"--user={args['--user']}",
                      f"--verifySSL={args['--verifySSL']}"]
        if len(newArgs) > 0:
            finalArgs += newArgs
        for arg in reviewArgs:
            finalArgs.append(arg.strip())
        menu = grapeMenu.menu(workspace_dir=self.workspace_dir)
        return menu.applyMenuChoice("review", finalArgs)

    def markReviewAsInProgress(self, args):
        logging.info("Prepending pull request title with **IN PROGRESS**...")
        return self.markReview(args, ["--title=**IN PROGRESS** ", "--prepend"], "Skipping marking pull request "
                                                                                "as IN PROGRESS...")

    def markReviewWithVersionNumber(self, args):
        version = self.progress["version"]
        logging.info(f"Prepending pull request title with {version}")
        return self.markReview(args, [f"--title={version} :", "--prepend"],
                              "Skipping marking pull request with version number")

    def ensureReview(self, args):
        return self.markReview(args, [], "Skipping ensuring review exists.", updateOnly=False)

    @property
    def codeReviews(self):
        if self._codeReviews is None:
            self._codeReviews = CodeReviewsFactory.makeCodeReviews(
                username=self.args["--user"], url=self.args["--codeReviewsURL"],
                verify=self.args["--verifySSL"], port=int(self.args["--ssh_pat_port"]),
                ssh_path = self.args["--ssh_pat_url"], workspace_dir=self.workspace_dir)
        return  self._codeReviews

    @property
    def repo(self):
        if self._repo is None:
            self._repo = self.codeReviews.project(self.args["--project"]).repo(self.args["--repo"])
        return self._repo

    def pullRequests(self):
        return self.repo.pullRequests()

    def openPullRequest(self):
        return self.repo.getOpenPullRequest(self.args["--topic"], self.args["--public"])

    def checkInProgressLock(self, args):
        if args["--noReview"]:
            logging.info("Skipping In Progress Lock Check..")
            return True
        inProgressRequests = []
        for request in self.pullRequests():
            inProgress = "IN PROGRESS" in request.title()
            if inProgress:
                doesConflict = request.toRef() == args["--public"]
                if doesConflict:
                    inProgressRequests.append(request)
        if len(inProgressRequests) == 0:
            logging.info("No other pull requests are IN PROGRESS...")
            return True
        if len(inProgressRequests) == 1:
            thisRequest = self.openPullRequest()
            if thisRequest == inProgressRequests[0]:
                logging.info("The pull request for this branch is already in progress. Continuing...")
                return 2
            if not args["--mergeTrain"]:
                logging.info("The following pull request is already in progress:")
                logging.info(inProgressRequests[0])
                return False
            else:
                return True
        else:
            if not args["--mergeTrain"]:
                logging.error("ERROR: There are multiple pull requests in progress!")
                for request in inProgressRequests:
                    logging.info(request)
                return False
            else:
                thisRequest = self.repo.getOpenPullRequest(args["--topic"], args["--public"])
                for request in inProgressRequests:
                    if thisRequest == request:
                        logging.info("The pull request for this branch is already in progress. Continuing...")
                        return 2
                logging.info("This pull request is not yet marked in progress.")
                return True


    def acquireInProgressLock(self, args):
        if args["--noReview"]:
            logging.info("Skipping In Progress Lock Check..")
            return True
        retcode = self.checkInProgressLock(args)
        if retcode:
            # the 2 means we are already marked as in progress
            return ((retcode == 2) or self.markReviewAsInProgress(args)) and self.checkInProgressLock(args)
        else:
            return False

    def releaseInProgressLock(self, args):
        if args["--noReview"]:
            logging.info("Skipping In Progress Lock Release...")
            return True
        request = self.openPullRequest()
        state = "open"
        if not request:
            matchingRequests = self.repo.getMergedPullRequests(args["--topic"], args["--public"])
            state = "merged"
            for r in matchingRequests:
                if "**IN PROGRESS**" in r.title():
                    request = r
                    break
        if request:
            title = re.sub("^.*\*\*IN PROGRESS\*\* *", "", request.title())
            return self.markReview(args, [f"--title={title}", f"--state={state}"], "")
        else:
            logging.warning("WARNING: No Open or Merged IN PROGRESS pull request found. Continuing...")
        return True

    def verifyCompletedReview(self, args):
        if args["--noReview"]:
            logging.info("Skipping verification of code review...")
            self.progress["reviewers"] = "No reviewers"
            return True
        pullRequest = self.openPullRequest()
        verified = False
        if pullRequest:
            verified = pullRequest.approved()
            reviewers = pullRequest.reviewers()
            if not verified:
                if not reviewers:
                    logging.info(
                        "There are no reviewers for your pull request for " +
                        f"{args['--topic']} targeting {args['--public']}.")
                    self.progress["reviewers"] = "No reviewers"
                else:
                    logging.info("The following reviewers have not approved your request:\n")
                    approvedReviewerNames = []
                    for reviewer in reviewers:
                        if reviewer[1] is False:
                            logging.info(f"{reviewer[0]} ({reviewer[2]})")
                        else:
                            approvedReviewerNames.append(reviewer[2])
                    if len(approvedReviewerNames) > 0:
                        self.progress["reviewers"] = ", ".join(approvedReviewerNames)
                    else:
                        self.progress["reviewers"] = "No reviewers"
            else:
                logging.info("All reviewers have approved your request.")
                if args["--user"] != pullRequest.author():
                    reviewers.append((pullRequest.author(), True, pullRequest.authorName()))
                self.progress["reviewers"] = ", ".join(x[2] for x in reviewers)
        else:
            url = git.join_list_as_git_path([codeReviews.url, "projects",
                                            args["--project"], "repos",
                                            args["--repo"], "pull-requests"])
            logging.info(
                "There is no pull request for your current branch.\n" +
                f"Start one using grape review or by visiting {url}")
            self.progress["reviewers"] = "No reviewers"
        return verified

    def testForCleanWorkspace(self, args):
        logging.info("Checking to make sure workspace has a clean status.")
        ret = utility.isWorkspaceClean(printOutput=True,
                                       workspace_dir=self.workspace_dir)
        menu = grapeMenu.menu(workspace_dir=self.workspace_dir)
        ret = menu.applyMenuChoice("status", ["--failIfInconsistent"]) and ret
        if ret:
            cb = git.currentBranch(execution_path=self.workspace_dir)
            topic = args["--topic"]
            ret = ret and cb == topic
            if not ret:
                logging.info(
                    f"Current branch {cb} is not topic branch {topic}. " +
                    f"Please checkout {topic} before publishing. ")
        return ret

    def performCICheck(self, args):
        """
        The purpose of this check is to allow the publish process to use the fact that the result of a
        merge between this branch and the public branch as they are right now did in fact past testing
        on the server to skip the test in the local environment.
        """
        ci_jobs = args["--testCIJob"]
        if ci_jobs:
            ci_jobs = ci_jobs.split(',')
        else:
            # If the user did not explicitly name their CI jobs that count as building and testing,
            # then this logic just skips the investigation of whether those jobs passed or not, avoiding
            # unnecessary communication with the Gitlab server.
            # if there are no jobs to check against, short-circuit
            self.progress["CIPassed"] = False
            return True
        
        passed = True
        for job in ci_jobs:
            successful_job = self.repo.getSuccessfulJob(job,
                                                        git.SHA(args["--topic"], execution_path=self.workspace_dir),
                                                        git.SHA(args["--public"], execution_path=self.workspace_dir),
                                                        args["--topic"],
                                                        args["--public"]
                                                        )
            passed = successful_job != None
            if not passed:
                logging.info("no successful job found.")
            # if user has configured a list of CIRepos that need to be active during CI jobs, we verify the
            # job has produced a GRAPE_PROJECT_SHA.json artifact and that all grape projects (top level and nested)
            # are consistent with our current workspace
            config = config_parser_global.grapeConfig()
            if passed and config.get(self.SECTION_WORKSPACE, "CIRepos"):
                logging.info("downloading artifact GRAPE_PROJECT_SHA.json from successful job...")
                artifact = json.loads(successful_job.artifact("GRAPE_PROJECT_SHA.json"))
                logging.info("...downloaded.")
                logging.info(f"verifying {artifact} is consistent with current workspace.")
                menu = grapeMenu.menu(workspace_dir=self.workspace_dir)
                passed = menu.getOption("uv").verifySHAList(artifact)
        self.progress["CIPassed"] = passed 
        if passed:
            logging.info(f'CI jobs {ci_jobs} passed, GRAPE PUBLISH will skip build and test steps')
        return True

    def performCustomStep(self, prefix, args):
        if not args[f"--{prefix}Cmds"]:
            return True
        if args[f"--{prefix}Dir"]:
            working_dir = os.path.join(self.workspace_dir, args[f"--{prefix}Dir"])
        else:
            working_dir = os.getcwd()

        cmds = args[f"--{prefix}Cmds"].split(',')
        logging.info("GRAPE PUBLISH - PERFORMING CUSTOM " +
                              f"{prefix.upper()} STEP")
        for cmd in cmds:
            if "<version>" in cmd:
                self.loadVersion(args)
                verStr = self.progress["version"]
                cmd = cmd.replace("<version>", verStr)
            if "<public>" in cmd:
                cmd = cmd.replace("<public>", args["--public"])

            capture_output = args["--quiet"]
            process_result = vine_subprocess.executeSubProcess(
                cmd.strip(), capture_output=capture_output, working_dir=self.workspace_dir)
            logging.info(process_result.returncode)
            if process_result.returncode != 0:
                if process_result.stdout:
                    logging.info(process_result.stdout.decode().strip())
                if process_result.stderr:
                    logging.error(process_result.stderr.decode().strip())
                return False
        return True

    def performCustomBuildStep(self, args):
        
        return (self.progress["CIPassed"] or self.performCustomStep("build", args)) and self.checkInProgressLock(args)

    def performCustomTestStep(self, args):
        return (self.progress["CIPassed"] or self.performCustomStep("test", args)) and self.checkInProgressLock(args)

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
            git.commit(f" -m \"{args['-m']}\"",
                       execution_path=self.workspace_dir)
        except grape_errors.GrapeGitError:
            pass

        return self.checkInProgressLock(args)

    def performCustomPostPublishSteps(self, args):
        return self.performCustomStep("postpublish", args)

    @staticmethod
    def getModifiedFileList(public, topic, args, *, execution_path):
        # Limit the number of updated files displayed per subproject
        emailMaxFiles = args["--emailMaxFiles"]
        try:
            updatelist = git.diff(f"--name-only {public} {topic}",
                                  execution_path=execution_path).split('\n')
        except:
            # Ensure branches are on working tree, then retry diff.
            current_branch = git.currentBranch(execution_path=execution_path)
            git.checkout(public, execution_path=execution_path)
            git.checkout(topic, execution_path=execution_path)
            git.checkout(current_branch, execution_path=execution_path)
            updatelist = git.diff(f"--name-only {public} {topic}",
                                  execution_path=execution_path).split('\n')
        if len(updatelist) > int(emailMaxFiles):
            updatelist.append("[ Additional files not shown ]")
        return updatelist

    def loadModifiedFiles(self, args):
        if "modifiedFiles" in self.progress:
            return True

        public = args["--public"]
        if args["--sendEmail"]:
            topic = self.progress["MR_tag"]
        else:
            topic = args["--topic"]
            if git.SHA(public, execution_path=self.workspace_dir) == \
                    git.SHA(topic, execution_path=self.workspace_dir):
                public = utility.userInput(
                    "Please enter the branch name or SHA of the commit to diff " +
                    f"against {topic} for the modified file list.")

        self.progress["modifiedFiles"] = []

        # Get list of modified files in main repo
        self.progress["modifiedFiles"] += self.getModifiedFileList(
            public, topic, args, execution_path=self.workspace_dir)

        # Get list of modified files in submodules
        # TODO: figure out how to get modified submodule files during post-push CI workflow
        if args["--recurse"]:
            submodulePublic = args["--submodulePublic"]
            submodules = git.getModifiedSubmodules(
                self.workspace_dir, public, topic, includeAdded=True)
            for sub in submodules:
                execution_path = os.path.join(self.workspace_dir, sub)
                self.progress["modifiedFiles"] += [os.path.join(sub, s) for s in self.getModifiedFileList(submodulePublic, topic, args, execution_path=execution_path)]

        # Get list of modified files in nested subprojects
        for nested in config_parser_user.getAllActiveNestedSubprojectPrefixes(workspaceDir=self.workspace_dir):
            execution_path = os.path.join(self.workspace_dir, nested)
            modified = self.getModifiedFileList(public, topic, args, execution_path=execution_path)
            if len(modified) > 0:
                self.progress["modifiedFiles"] += [os.path.join(nested, s) for s in modified]

        return True

    def loadVersion(self, args):
        if "version" not in self.progress:
            if args["--mergeTrain"] and not args["--sendEmail"]:
                thisRequest = self.openPullRequest()
                iid = thisRequest.iid()
                version = f"MR_{iid}"
                self.progress["version"] = version
                return True
            else:
                menu = grapeMenu.menu(workspace_dir=self.workspace_dir)
                menu.applyMenuChoice("version", ["read"])
                guess = menu.getOption("version").ver
                self.progress["version"] = utility.userInput("Please enter version string for this commit", guess)
                logging.info(f"version is {self.progress['version']}")
        return True

    def loadMajorAndMinorVersion(self, args):
        menu = grapeMenu.menu(workspace_dir=self.workspace_dir)
        menu.applyMenuChoice("version", ["read"])
        self.progress["major_version"] = menu.getOption("version").major_ver
        self.progress["minor_version"] = menu.getOption("version").minor_ver
        logDir = args["--updateLogDir"]
        if "<major_version>" in logDir:
            logDir = logDir.replace("<major_version>", f"{self.progress['major_version']}")
        if "<minor_version>" in logDir:
            logDir = logDir.replace("<minor_version>", f"{self.progress['minor_version']}")
        args["--updateLogDir"] = logDir

        
    def loadCommitMessageFromRecentMergeRequest(self, args):
        tag = git.describe(f"origin/{args['--topic']} --first-parent --match=MR_*", execution_path=self.workspace_dir)
        tag = tag.split('-')[0]
        self.progress["MR_tag"] = tag
        pr_id = tag.split("MR_")[1]
        pull_request = self.repo.pullRequests(id=pr_id)[0]
        escapedCommitMsg = pull_request.description().decode('ascii').splitlines(True)+['\n']
        escapedCommitMsg = ''.join(escapedCommitMsg).replace("\"", "\\\"")
        escapedCommitMsg = escapedCommitMsg.replace("`", "'")
        self.progress["commitMsg"] = escapedCommitMsg
        self.progress["reviewers"] = ", ".join(x[2] for x in pull_request.reviewers())
        args["-m"] = escapedCommitMsg
        return True
             

    def loadCommitMessage(self, args):
        if args["--sendEmail"]:
            return self.loadCommitMessageFromRecentMergeRequest(args)
        if "reviewers" not in self.progress:
            # fill in the reviewers entry in progress, but don't check the review status.
            self.verifyCompletedReview(args)
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
                with io.open(commitMsgFile, 'r') as f:
                    commitMsg = f.readlines()+["\n"]

            except IOError as e:
                logging.error(e.message)
                logging.error(f"Could not read contents of {commitMsgFile}")
                args["<CommitMessageFile>"] = False
                return False

            if not args["--noReview"]:
                logging.info("Updating Pull Request with commit msg...")
                self.markReview(args, ["--descr", commitMsgFile], "")
            else:
                logging.info("Skipping update of pull request description from commit message")
        elif args["-m"]:
            commitMsg = [args["-m"]+"\n"]
        else:
            if args["--noReview"]:
                logging.info("Skipping retrieval of commit message from Pull Request description..")
                if not args["-m"]:
                    logging.info("File with commit message is required " +
                                 "argument when publishing with --noReview " +
                                 "and no -m <msg> defined.")
                    return False
            logging.info("Retrieving pull request description for use as commit message...")
            pullRequest = self.openPullRequest()
            if pullRequest:
                commitMsg = pullRequest.description().decode('ascii').splitlines(True)+['\n']
            else:
                commitMsg = ""

        # this will be used for the actual merge commit message.
        escapedCommitMsg = ''.join(commitMsg).replace("\"", "\\\"")
        escapedCommitMsg = escapedCommitMsg.replace("`", "'")

        if escapedCommitMsg:
            args["-m"] = escapedCommitMsg
        else:
            logging.warning("WARNING: Commit message is empty. ")

        logging.info("The following commit message will be used for email notification, merge commits, etc.\n"
                         "======================================================================")
        logging.info(''.join(commitMsg[:10]))
        logging.info("======================================================================")
        proceed = utility.userInput("Is the above message what you want for email notifications and merge commits? "
                                    "['y','n']", 'y')
        if not proceed:
            logging.info("Stopping. Either edit the message in your pull request, or pass in the name of a file "
                             "containing your message as an argument to grape publish.")
            e = Exception()
            e.message = "Invalid commit message."
            args["<CommitMessageFile>"] = False
            args["-m"] = False
            raise e
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
        self.loadMajorAndMinorVersion(args)
        logDir = args["--updateLogDir"]
        if logDir:
            if not os.path.exists(logDir):
                os.makedirs(logDir)
            logFile = os.path.join(logDir,f"{logFile}_{self.progress['version']}")
        if logFile:
            header = args["--entryHeader"]
            header = header.replace("<date>", time.asctime())
            header = header.replace("<user>", git.config(
                "--get user.name", execution_path=self.workspace_dir))
            header = header.replace("<version>", self.progress["version"])
            header = header.replace("<reviewers>", self.progress["reviewers"])
            header = ["\n"]+header.split("\\n")
            commitMsg = header + commitMsg
            numLinesToSkip = int(args["--skipFirstLines"])
            logFilePath = os.path.join(self.workspace_dir,logFile)
            loglines = []
            if not logDir:
                with io.open(logFilePath, 'r') as f:
                    loglines = f.readlines()
                updated_or_added  = "updated"
            else:
                updated_or_added = "added"
            loglines.insert(numLinesToSkip, '\n'.join(commitMsg))
            with io.open(logFilePath, 'w') as f:
                f.writelines(loglines)
            git.add(f"{logFilePath}", execution_path=self.workspace_dir)
            git.commit(f"{logFile} -m \"GRAPE publish: {updated_or_added} log file " +
                       f"{logFile}\"", execution_path=self.workspace_dir)
        return self.checkInProgressLock(args)

    def mergeUpdateLogs(self, args):
        startVer = args["--startVersion"]
        stopVer = args["--stopVersion"]
        menu = grapeMenu.menu(workspace_dir=self.workspace_dir)
        versionOption = menu.getOption("version")
        if stopVer is None:
            versionArgs = ["read"]
            menu.applyMenuChoice("version", versionArgs)
            stopVer = menu.getOption("version").ver
        if args["--tagSuffix"] is None:
            config = config_parser_global.grapeConfig()
            branch2suffix = config.getMapping(self.SECTION_VERSIONING, "branchtagsuffixmappings")
            args["--tagSuffix"] = branch2suffix[git.currentBranch(execution_path=self.workspace_dir)]
        startSlots = versionOption.convertTagStringToSlots(args["--tagPrefix"], args["--tagSuffix"], startVer)
        stopSlots = versionOption.convertTagStringToSlots(args["--tagPrefix"], args["--tagSuffix"], stopVer)
        # we will only merge update logs over the last slot
        mergedLogLines =  []
        slotArgs = {"--prefix":args["--tagPrefix"],"--suffix":args["--tagSuffix"]}
        while stopSlots[-1] >= startSlots[-1]:
            ver2 =  versionOption.slotsToString(slotArgs, stopSlots)
            stopSlots[-1] = stopSlots[-1] - 1
            ver1 =  versionOption.slotsToString(slotArgs, stopSlots)
            self.loadMajorAndMinorVersion(args)
            log_files = git.diff(f"--name-only {ver1} {ver2} -- {args['--updateLogDir']}", execution_path=self.workspace_dir)
            log_files = log_files.split()
            for lf in log_files:
                mr_ver = lf.split(args["--updateLogDir"]+os.path.sep)[1].split(args["--updateLog"]+'_')[1]
                with open(lf) as f:
                    file_lines = f.readlines()
                for l in file_lines:
                    if l == f"{mr_ver}\n":
                        mergedLogLines.append(f"{ver2}\n")
                    else:
                        mergedLogLines.append(l)
        with open(args["--mergedLog"],'w') as f:
            for l in mergedLogLines:
                f.write(l)
        return True


    def tickVersion(self, args):
        if not args["--tickVersion"]:
            return True
        menu = grapeMenu.menu(workspace_dir=self.workspace_dir)
        if not args["--noReview"]:
            thisRequest = self.openPullRequest()
            requestTitle = thisRequest.title()
            versionArgs = ["read"]
            menu.applyMenuChoice("version", versionArgs)
            currentVer = menu.getOption("version").ver
            if currentVer in requestTitle:
                logging.info(f"Current Version string '{currentVer}' already in pull request title '{requestTitle}'. Assuming this is from "
                "a previous call to grape publish. Not ticking version again.")
                return True
        ret = True
        if args["--tickVersion"]:
            versionArgs = ["tick", "--notag", f"--public={args['--public']}"]
            for arg in args["-T"]:
                versionArgs += [arg.strip()]
            ret = menu.applyMenuChoice("version", versionArgs)
            self.progress["version"] = menu.getOption("version").ver
            ret = ret and self.markReviewWithVersionNumber(args)
        return ret and self.checkInProgressLock(args)

    def tagVersion(self, args):
        if not self.loadVersion(args):
            return False
        if not args["--tickVersion"]:
            return True
        if 'workspace_dir' not in args:
            logging.error("Failed to Tag Version. Workspace dir not given.")
            raise Exception
        versionArgs = ["tick", self.progress["version"], "--tag", "--notick", "--nocommit", "--tagNested"]
        if args["--mergeTrain"]:
            versionArgs.append("--tagPrefix=MR_")
            versionArgs.append("--prefix=MR_")

        for arg in args["-T"]:
            versionArgs += [arg.strip()]
        menu = grapeMenu.menu(workspace_dir=self.workspace_dir)
        ret = menu.applyMenuChoice("version", versionArgs)
        for nested in config_parser_user.getAllActiveNestedSubprojectPrefixes(workspaceDir=self.workspace_dir):
            nested_dir = os.path.join(args['workspace_dir'], nested)
            git.push("--tags origin", execution_path=nested_dir)
        git.push("--tags origin", execution_path=args['workspace_dir'])
        return ret

    def sendNotificationEmail(self, args):

        if not (self.loadCommitMessage(args) and self.loadVersion(args) and self.loadModifiedFiles(args)):
            return False
        # Write the contents of the mail file out to a temporary file
        mailfile = os.path.realpath(tempfile.mktemp())

        with io.open(mailfile, 'w') as mf:
            date = time.asctime()
            emailHeader = args["--emailHeader"]
            emailHeader = emailHeader.replace(
                "<user>", git.config("--get user.name", execution_path=self.workspace_dir))
            emailHeader = emailHeader.replace("<date>", date)
            emailHeader = emailHeader.replace("<version>", self.progress["version"])
            emailHeader = emailHeader.replace("<reviewers>", self.progress["reviewers"])
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
            mf.write('\n')
            emailFooter = args["--emailFooter"]
            emailFooter = emailFooter.replace(
                "<user>", git.config("--get user.name", execution_path=self.workspace_dir))
            emailFooter = emailFooter.replace("<date>", date)
            emailFooter = emailFooter.replace("<version>", self.progress["version"])
            emailFooter = emailFooter.replace("<reviewers>", self.progress["reviewers"])
            emailFooter = emailFooter.replace("<public>", args["--public"])
            emailFooter = emailFooter.split("\\n")
            mf.write('\n'.join(emailFooter))

        if not args["--emailNotification"].lower() == "true":
            logging.info("Skipping E-mail notification..")
            with io.open(mailfile, 'r') as mf:
                logging.info("-- Begin update message --")
                logging.info(mf.read())
                logging.info("-- End update message --")
            return True

        # Open the file back up and attach it to a MIME message
        with io.open(mailfile, 'r') as t:
            message = t.read()
        msg = MIMEText(message)

        # Use their email address from their git user profile.
        myemail = git.config("--get user.email",
                             execution_path=self.workspace_dir)
        mailsubj = args["--emailSubject"]
        mailsubj = mailsubj.replace(
            "<user>", git.config("--get user.name", execution_path=self.workspace_dir))
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
        try:
            server = args["--emailServer"]
            s = smtplib.SMTP(server, timeout=10)
        except socket.error as e:
            logging.error(f"Failed to email: {e}")
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

    def askWhetherToDelete(self, args):
        if "<<doDelete>>" in self.progress:
            self.doDelete = self.progress["<<doDelete>>"]
        if not self.doDelete:
            if args["--deleteTopic"].lower() == "true":
                self.doDelete[args["--topic"]] = utility.userInput(
                    "Once the publish is done, would you like to delete " +
                    f"the branch {args['--topic']} ?\n[y/n]",
                    default='y')
            else:
                self.doDelete[args["--topic"]] = False
        self.progress["<<doDelete>>"] = self.doDelete

    def deleteTopicBranch(self, args):
        self.askWhetherToDelete(args)
        if self.doDelete[args["--topic"]]:
            logging.info(f"Deleting {args['--topic']}")
            menu = grapeMenu.menu(workspace_dir=self.workspace_dir)
            menu.applyMenuChoice("db", [args["--topic"]])
        # If the branch was not deleted, offer to return to that branch
        try:
            # SHA will raise an exception if the branch has been deleted
            if git.SHA(args["--topic"], execution_path=self.workspace_dir):
                checkout = utility.userInput(
                    f"You are currently on {git.currentBranch(execution_path=self.workspace_dir)}. " +
                    f"Would you like to checkout {args['--topic']}? [y,n]",
                    "n")
                # 'checkout' is bool or the user's input. Enforces 'y' given.
                if checkout is True:
                    menu = grapeMenu.menu(workspace_dir=self.workspace_dir)
                    menu.applyMenuChoice("checkout", [args["--topic"]])
        except:
            pass
        return True

    @staticmethod
    def validateInput(policy, args):
        policy = policy.strip().lower()
        valid = False
        if policy == "merge" or policy == "squash":
            valid = bool(args["-m"])
            logging.info(args["-m"])
            if not valid:
                logging.info("Commit message required for merge or squash merge publish policies.")
        if policy == "rebase":
            valid = True
        if not valid:
            logging.info("Type grape publish -h for more details")
        return valid

    def remoteMerge(self, public, topic, repo, args, isSubmodule, isNested):
        codeReviews = self.codeReviews(args)
        remoteRepo = codeReviews.repoFromWorkspaceRepoPath(repo,
                                                        isSubmodule=isSubmodule,
                                                        isNested=isNested)
        pr = remoteRepo.getOpenPullRequest(topic, public)
        if pr is not None:
            logging.info(f"remotely merging {topic} into {public}")
            if pr.merge():
                git.checkout(execution_path=public)
                git.pull("", execution_path=self.workspace_dir)
                logging.info(f"{topic} merged successfully to {public}")
                logging.info(f"You are currently on {public}")
                return True
            logging.info("Failed to do a remote merge.")
        else:
            logging.info(
                f"Could not find open Pull Request for {topic} in {repo}")
        return False

    @staticmethod
    def merge(public, topic, repo, args):
        logging.info(f"merging {topic} into {public}")
        git.push(f". {topic}:{public}", execution_path=repo)
        git.checkout(public, execution_path=repo)
        logging.info(f"{topic} merged successfully to {public}")
        logging.info(f"You are currently on {public}")

    @staticmethod
    def squashMerge(public, topic, repo, args):
        logging.info(f"squash merging {topic} into {public}")
        git.checkout(public, execution_path=repo)
        git.merge(f"--squash {topic}", execution_path=repo)
        git.commit(f"-m \"{args['-m']}\"", execution_path=repo)
        logging.info(f"{topic} squash-merged successfully to {public}")
        logging.info(f"You are currently on {public}")

    @staticmethod
    def rebase(public, topic, repo):
        logging.info(f"rebasing {topic} onto {public}")
        git.rebase(public, execution_path=repo)
        logging.info(f"{topic} successfully rebased onto {public}")
        git.checkout(public, execution_path=repo)
        git.merge(topic, execution_path=repo)
        logging.info(f"You are currently on {public}")

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

    def performCascade(self, status, args, mergeID, repo, branch, public):
        if mergeID not in status:
            status[mergeID] = "READY"
        if status[mergeID] == "DONE":
            return True
        if status[mergeID] == "READY":
            git.checkout(branch, execution_path=self.workspace_dir)
            status[mergeID] = "SWITCHED"
        if status[mergeID] == "SWITCHED":
            status[mergeID] = "MERGING"
            try:
                git.merge(f"{public} -m \"GRAPE PUBLISH: cascade merge of " +
                          f"{public} to {branch} after publish.\"",
                          execution_path=self.workspace_dir)
                status[mergeID] = "MERGED"
            except grape_errors.GrapeGitError as e:
                if e.has_conflict():
                    logging.error(
                        f"Conflicts generated in cascade merge from {public}" +
                        f" to {branch} in {repo}.\nPlease use git " +
                        "mergetool to resolve, and then git commit to commit" +
                        " your changes.\nOnce done, please run grape publish " +
                        "--continue .")
                return False

        if status[mergeID] == "MERGING":
            clean = self.testForCleanWorkspace(args)
            if clean:
                logging.info("Resuming with cascades...")
                status[mergeID] = "MERGED"
            if not clean:
                logging.info("Workspace not clean after resuming from a cascade.\n"
                                 "Please commit your merge resolution or otherwise clean up your workspace.")
                return False
        if status[mergeID] == "MERGED":
            public = branch
            git.push(f"origin {branch}", execution_path=self.workspace_dir)
            status[mergeID] = "PUSHED"
        if status[mergeID] == "PUSHED":
            if "outer" in mergeID and args["--tickOnCascade"] > 0:
                menu = grapeMenu.menu(workspace_dir=self.workspace_dir)
                menu.applyMenuChoice(
                    "version", ["tick", "--tag", f"--slot={args['--tickOnCascade']}"])
                git.push("--tags origin", execution_path=self.workspace_dir)
            status[mergeID] = "DONE"
        return True

    def performCascades(self, args):
        self.loadPublishTargets(args)

        if "<<cascadeDict>>" in args and args["<<cascadeDict>>"]:
            self.cascadeDict = args["<<cascadeDict>>"]
        if "<<cascadeMergeStatus>>" not in args:
            args["<<cascadeMergeStatus>>"] = {}
        status = args["<<cascadeMergeStatus>>"]
        if self.cascadeDict:
            # do outer level and nested project cascades
            cascade = self.cascadeDict["outer"]
            repos= [""] + config_parser_user.getAllActiveNestedSubprojectPrefixes(workspaceDir=self.workspace_dir)
            repos = [os.path.join(self.workspace_dir, r) for r in repos]
            for repo in repos:
                public = args["--public"]
                with self.temp_work_in_dir(repo):
                    for branch in cascade:
                        mergeID = f"outer_{repo}_{branch}"
                        if not self.performCascade(status, args, mergeID, repo, branch, public):
                            return False

            if "submodules" in self.cascadeDict and "<<publishedSubmodules>>" in args:
                cascade = self.cascadeDict["submodules"]
                repos = [os.path.join(self.workspace_dir, r) for r in args["<<publishedSubmodules>>"]]
                for repo in repos:
                    public = args["--submodulePublic"]
                    with self.temp_work_in_dir(repo):
                        for branch in cascade:
                            mergeID = f"submodules_{repo}_{branch}"
                            if not self.performCascade(status, args, mergeID, repo, branch, public):
                                return False

        return True



    def publish(self, policy, public, topic, repo, args, isSubmodule=False, isNested=False):
        # don't bother publishing if public and topic are the same commit
        if git.shortSHA(public, execution_path=repo).strip() \
                == git.shortSHA(topic, execution_path=repo).strip():
            git.checkout(public, execution_path=repo)
            return
        policy = policy.strip().lower()
        if policy == "merge":
            if args["--remoteMerge"]:
                try:
                    if self.remoteMerge(public, topic, repo, args, isSubmodule, isNested):
                        return
                    else:
                        logging.error(
                            f"Bitbucket seems to think {topic} in {repo} " +
                            "is not mergeable... aborting")
                        raise Exception
                except stashyErrors.GenericException as e:
                    logging.warning("WARNING: Remote merge failed. Attempting local merge instead.")
                    self.merge(public, topic, repo, args)
            else:
                self.merge(public, topic, repo, args)
        elif policy == "squash":
            self.squashMerge(public, topic, repo, args)
        elif policy == "rebase":
            self.rebase(public, topic, repo)

        if not args["--nopush"]:
            try:
                git.push("-u origin HEAD", throwOnFail=True, execution_path=repo)
            except grape_errors.GrapeGitError as e:
                if e.commError:
                    logging.error("Unable to push result of publish to origin due to connectivity issue.")
                raise e

    def loadPublishTargets(self, args):
        config = config_parser_global.grapeConfig()
        public = args["--public"]
        topic = args["--topic"]

        # decide whether to recurse into submodules
        recurse = config.get(self.SECTION_WORKSPACE, 'manageSubmodules')
        if args["--recurse"]:
            recurse = True
        if args["--noRecurse"]:
            recurse = False

        args["--recurse"] = recurse
        if args["--recurse"]:
            if not args["--submodulePublic"]:
                submapping = config.getMapping(self.SECTION_WORKSPACE, 'submoduleTopicPrefixMappings')
                submodulePublic = submapping[self.branchPrefix]
                args["--submodulePublic"] = submodulePublic

        # deal with subtrees
        push_subtrees = config.getboolean(self.SECTION_SUBTREES, 'pushOnPublish') or args["--pushSubtrees"]
        push_subtrees = push_subtrees and not args["--noPushSubtrees"]
        args["--pushSubtrees"] = push_subtrees
        if push_subtrees:
            allsubtrees = config.get(self.SECTION_SUBTREES, 'names').strip().split()
            self.modifiedSubtrees = self.modifiedSubtrees.union(set(args["--forcePushSubtree"]))
            for st in allsubtrees:
                prefix = config.get(f'subtree-{st}', 'prefix')
                if git.diff(f"--name-only {public} {topic} -- " +
                            f"{os.path.join(self.workspace_dir, prefix)}",
                            execution_path=self.workspace_dir):
                    self.modifiedSubtrees.add(st)
            for st in self.modifiedSubtrees:
                self.st_prefixes[st] = config.get(f'subtree-{st}', 'prefix')
                self.st_remotes[st] = git.parseSubprojectRemoteURL(
                    config.get(f'subtree-{st}', 'remote'),
                    execution_path=self.workspace_dir)
                self.st_branches[st] = config.getMapping(f'subtree-{st}', 'topicPrefixMappings')[topic]

        # deal with nested subprojects. 'workspaceDir' is None on purpose.
        self.modifiedNestedProjects = config_parser_user.getAllModifiedNestedSubprojectPrefixes(public, workspaceDir=self.workspace_dir)

        self.modifiedOuter = True if git.log(f"--oneline {public}..{topic}", execution_path=self.workspace_dir) else False

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
        submodules = git.getModifiedSubmodules(self.workspace_dir, public,
                                               topic, includeAdded=True)

        userMsg = f"GRAPE: When ready, grape will publish {topic} to:\n"

        useAnd = False
        if recurse:
            newline_and_tabs = '\n\t\t'
            if submodules:
                spaced_submodules = newline_and_tabs.join(submodules)
                userMsg += f"{args['--submodulePublic']} for the "
                userMsg += f"following submodules:{newline_and_tabs}"
                userMsg += f"{spaced_submodules}\n"
                useAnd = True

            if self.modifiedNestedProjects:
                spaced_prefixes = newline_and_tabs.join(self.modifiedNestedProjects)
                userMsg += f"{public} for the following nested "
                userMsg += f"subprojects:{newline_and_tabs}{spaced_prefixes}\n"
                useAnd = True

        if self.modifiedOuter:
            maybe_and = "and " if useAnd else ""
            userMsg += f"{maybe_and}{public} for the outer level repo.\n"

        push_subtrees = args["--pushSubtrees"]
        if push_subtrees:
            if self.modifiedSubtrees:
                userMsg += "Additionally, grape will publish the following subtrees to the following destinations:\n"
                for st in self.modifiedSubtrees:
                    userMsg += f"subtree: {self.st_prefixes[st]}\t"
                    userMsg += f"repo: {self.st_remotes[st]}\t"
                    userMsg += f"branch:{self.st_branches[st]}\n"

        proceed = utility.userInput(f"{userMsg}\nProceed? [y/n]", 'y')
        if not proceed:
            return False
        self.progress["targetsVerified"] = True
        # get the commit message here as well.
        if not self.loadCommitMessage(args):
            return False
        self.askWhetherToDelete(args)
        return True

    def publishAllProjects(self, args):
        # make sure we have a commit message
        if not (self.loadCommitMessage(args) and self.loadPublishTargets(args)):
            return False
        public = args["--public"]
        topic = args["--topic"]
        recurse = args["--recurse"]
        config = config_parser_global.grapeConfig()

        # make sure public branch is up to date.
        grapeMenu.menu().applyMenuChoice('up', ['up', f'--public={public}'])

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
            policy = self.parseConfigPublishPolicy(args, config.getMapping(self.SECTION_FLOW, 'publishPolicy')[public], topic)

        self.parseCascadeArgs(args)

        if recurse:
            submodulePublic = args["--submodulePublic"]
            activeSubmodules = git.getActiveSubmodules(execution_path=self.workspace_dir)
            modifiedSubmodules = git.getModifiedSubmodules(self.workspace_dir, public, topic, includeAdded=True)
            unmodifiedSubmodules = list(set(activeSubmodules) - set(modifiedSubmodules))

            # submodule policy is Command Line requested policy, otherwise is based on
            #       .grapeconfig.workspace.submodulePublishPolicy
            submodulePolicy = CLPolicy
            # store current value for args["--cascade"]
            outerCascadeOption = args["--cascade"]
            if not submodulePolicy:
                submodulePolicy = config.getMapping(self.SECTION_WORKSPACE, 'submodulePublishPolicy')[submodulePublic]
                submodulePolicy = self.parseConfigPublishPolicy(args, submodulePolicy, topic, repoType="submodule")

            valid = self.validateInput(submodulePolicy, args)
            if valid and self.verifyPublishTargetsWithUser(args):
                for sub in modifiedSubmodules:
                    subpath = os.path.join(self.workspace_dir, sub)
                    menu = grapeMenu.menu(workspace_dir=subpath)
                    menu.applyMenuChoice('up', ['up', '--noRecurse',
                                         f'--wd={subpath}',
                                         f'--public={submodulePublic}'])
                    with self.temp_work_in_dir(subpath):
                        self.publish(submodulePolicy, submodulePublic, topic, subpath, args, isSubmodule=True)
                    #add and commit any new merge commits in submodules as a result of the publish
                    git.add(sub, execution_path=self.workspace_dir)
                try:
                    # we are cool with this not working - only will have something to commit if the
                    # submodules were published without fast forward merges
                    git.commit(f"-m \"{args['-m']} - submodules published\"",
                               execution_path=self.workspace_dir)
                except grape_errors.GrapeGitError:
                    pass
                # ensure submodules that aren't modified end up on the public branch
                for sub in unmodifiedSubmodules:
                    git.checkout(submodulePublic,
                                 execution_path=os.path.join(self.workspace_dir, sub))

                # restore value for args["--cascade"]
                args["<<publishedSubmodules>>"] = modifiedSubmodules
                args["--cascade"] = outerCascadeOption


        # push subtrees to their respective remote branches
        push_subtrees = args["--pushSubtrees"]
        if push_subtrees:
            modifiedSubtrees = self.modifiedSubtrees
            if modifiedSubtrees:
                proceed = self.verifyPublishTargetsWithUser(args)
                if proceed:
                    squash = "--squash" if config.get(self.SECTION_SUBTREES, "mergepolicy").lower() == "squash" else ""
                    for st in modifiedSubtrees:
                        logging.info(
                            f"pushing subtree {self.st_prefixes[st]} " +
                            f"to {self.st_remotes[st]} " +
                            f"(branch {self.st_branches[st]})...")

                        try:
                            git.subtree(
                                f"push --prefix={self.st_prefixes[st]} " +
                                f"{self.st_remotes[st]} " +
                                f"{self.st_branches[st]} ",
                                execution_path=self.workspace_dir)
                        except grape_errors.GrapeGitError:
                            # the push can fail if there has never been a subtree add / pull in this repo.
                            logging.info("First attempt failed. Attempting a subtree pull then push...")
                            git.subtree(
                                f"pull {squash} " +
                                f"--prefix={self.st_prefixes[st]} " +
                                f"{self.st_remotes[st]} " +
                                f"{self.st_branches[st]} ",
                                execution_path=self.workspace_dir)
                            git.subtree(
                                f"push --prefix={self.st_prefixes[st]} " +
                                f"{self.st_remotes[st]} " +
                                f"{self.st_branches[st]} ",
                                execution_path=self.workspace_dir)
                            logging.info("Succeeded!")

        valid = self.validateInput(policy, args)
        if valid and self.verifyPublishTargetsWithUser(args):
            for nested in config_parser_user.getAllActiveNestedSubprojectPrefixes(workspaceDir=self.workspace_dir):
                self.publish(policy, public, topic, os.path.join(self.workspace_dir, nested), args, isNested=True)
            if self.modifiedOuter:
                self.publish(policy, public, topic, self.workspace_dir, args)
            else:
                git.checkout(public, execution_path=self.workspace_dir)
            return True
        return False

    def push(self, args):
        logging.info("pushing branch to trigger merge train pipeline.")
        menu = grapeMenu.menu(workspace_dir=self.workspace_dir)
        return menu.applyMenuChoice("push")

    def requestUserStartMergeTrain(self, args):
        thisRequest = self.openPullRequest()
        logging.info("********************************************************************************")
        logging.info("All changes pushed and ready for being enqueued into merge train.")
        logging.info("Gitlab does not yet support remote queuing into merge trains, please go to")
        logging.info(thisRequest.link())
        logging.info("and click on the 'Start merge train' button.")
        logging.info("********************************************************************************")
        return True


    def mergeOnSuccess(self, args):
        if not self.loadCommitMessage(args):
            return False
        thisRequest = self.openPullRequest()
        logging.info("Triggering merge on success of merge train pipeline.")
        try:
            success = thisRequest.merge(merge_commit_message=self.progress["commitMsg"],
                                 should_remove_source_branch=False,
                                 merge_when_pipeline_succeeds=True)
        except GitlabMRClosedError:
            time.sleep(5)
            logging.info("Trying again after initial 405 error...")
            try:
                success = thisRequest.merge(merge_commit_message=self.progress["commitMsg"],
                                     should_remove_source_branch=False,
                                     merge_when_pipeline_succeeds=True)
                logging.info("successful...")
            except GitlabMRClosedError:
                return False
        return success

