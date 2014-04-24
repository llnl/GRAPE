import os

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

    Usage: grape-publish [--squash [--cascade ] | --merge |  --rebase]
                         [-m <msg>]
                         [--recurse | --norecurse]
                         [<public> [<submodulePublic>]]
                         [--topic=<branch>]
                         [--noverify]
                         [--nopush]
                         [--pushSubtrees | --noPushSubtrees]
                         [-v]
                         [--startAt=<startStep>] [--stopAt=<stopStep>]
                         [--continue]
                         [--buildCmds=<buildStr>] [--buildDir=<path>]
                         [--testCmds=<testStr>] [--testDir=<path>]
                         [--tickVersion=<bool> [-T <arg>]...]
                         [--user=<StashUserName>]
                         [--project=<StashProjectKey>]
                         [--repo=<StashRepoName>]
                         [-R <arg>]...
                         [--noReview]
                         [--deleteTopic=<bool>]

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
    --buildCmds=<buildStr>  The comma-delimited list of build commands to execute.
                            [default: .grapeconfig.publish.buildCmds]
    --buildDir=<path>       The directory (relative to the workspace root directory) to execute the build steps in.
                            [default: .grapeconfig.publish.buildDir]
    --testCmds=<testStr>    The comma-delimited list of test commands to execute.
                            [default: .grapeconfig.publish.testCmds]
    --testDir=<path>        The directory (relative to the workspace root directory) to execute the test steps in.
                            [default: .grapeconfig.publish.testDir]
    --deleteTopic=<bool>    Delete the topic branch when done. [default: .grapeconfig.publish.deleteTopic]
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
    --noReview              Don't perform any actions that interact with pull requests.

    Optional Arguments:
    <public>                The branch to publish to. Defaults to the mapping for the current topic branch as described
                            by .grapeconfig.flow.topicPrefixMappings.
    <submodulePublic>       The branch to publish to in submodules. Defaults to the mapping for the current topic branch
                            as described by .grapeconfig.workspace.submoduleTopicPrefixMappings.

    Publish Steps:
    build :   Runs a custom build step.
    test:
    prePublish:
    tickVersion:
    publish:
    postPublish:
    deleteTopic:



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
        config.set('publish', 'buildDir', '')
        # test steps
        config.set('publish', 'testCmds', '')
        config.set('publish', 'testDir', '')
        # tick the version?
        config.set('publish', 'tickVersion', 'False')
        # delete when done
        config.set('publish', 'deleteTopic', 'False')

    def __init__(self):
        super(Publish, self).__init__()
        self._key = "publish"
        self._section = "Gitflow Tasks"
        self.branchPrefix = None

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
        if topic and topic != git.currentBranch():
            git.checkout(args["--topic"])
        if not topic:
            args["--topic"] = git.currentBranch()
        topic = args["--topic"]

        # resolve default public branch using .grapeconfig.flow.topicPrefixMappings
        config = grapeConfig.grapeConfig()
        prefix = git.branchPrefix(topic)
        public = args["<public>"]
        if not public:
            public = config.getPublicBranchFor(topic)
        args["<public>"] = public
        self.branchPrefix = prefix

    def execute(self, args):
        self.parseArgs(args)
        startPoint = args["--startAt"]
        order = ["verifyCompletedReview", "testForCleanWorkspace1", "markInProgress", "build", "test",
                 "testForCleanWorkspace2", "prePublish", "tickVersion", "publish", "postPublish",
                 "deleteTopic", "done"]
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
                 "publish": self.publishAllProjects,
                 "postPublish": self.performCustomPostPublishSteps,
                 "deleteTopic": self.deleteTopicBranch,
                 "verifyCompletedReview": self.verifyCompletedReview,
                 "testForCleanWorkspace1": self.testForCleanWorkspace,
                 "testForCleanWorkspace2": self.testForCleanWorkspace,
                 "markInProgress": self.markReviewAsInProgress}

        currentStep = startPoint
        for step in order:
            if step == "done":
                break
            if step == stopPoint:
                utility.printMsg("Stopping at %s step as requested." % stopPoint)
                break
            if step != currentStep:
                continue
            ret = steps[step](args)
            if ret:
                currentStep = order[order.index(currentStep) + 1]
            else:
                utility.printMsg("Publish step %s failed. Please resolve the issue and then continue using\n"
                                 "grape publish --continue" % step.upper())
                args["--startAt"] = step
                self.dumpProgress(args)
                return False

        return True

    def markReviewAsInProgress(self, args):
        if args["--noReview"]:
            utility.printMsg("Skipping marking pull request as IN PROGRESS...")
            return True
        utility.printMsg("Prepending pull request title with **IN PROGRESS**...")
        reviewArgs = args["-R"]
        newArgs = ["--title=**IN PROGRESS** ", "--prepend", "--source=%s" % args["--topic"]]
        for arg in reviewArgs:
            newArgs.append(arg.strip())

        return grapeMenu.menu().applyMenuChoice("review", newArgs)

    def markReviewWithVersionNumber(self, args):
        if args["--noReview"]:
            utility.printMsg("Skipping marking pull request with version number")
            return True
        version = git.describe("--abbrev=0")
        utility.printMsg("Prepending pull request title with %s" % version)
        reviewArgs = args["-R"]
        newArgs = ["--title=%s :" % version, "--source=%s" % args["--topic"], "--prepend"]
        for arg in reviewArgs:
            newArgs.append(arg.strip())
        return grapeMenu.menu().applyMenuChoice("review", newArgs)

    def verifyCompletedReview(self, args):
        if args["--noReview"]:
            utility.printMsg("Skipping verification of code review...")
            return True
        atlassian = Atlassian.Atlassian(username=args["--user"])
        repo = atlassian.project(args["--project"]).repo(args["--repo"])
        pullRequest = repo.getOpenPullRequest(args["--topic"], args["<public>"])
        verified = False
        if pullRequest:
            verified = pullRequest.approved()
            if not verified:
                reviewers = pullRequest.reviewers()
                if not reviewers:
                    utility.printMsg("There are no reviewers for your pull request.")
                else:
                    utility.printMsg("The following reviewers have not approved your request:\n")
                    for reviewer in reviewers:
                        if reviewer[1] is False:
                            print(reviewer[0])
            else:
                utility.printMsg("All reviewers have approved your request.")
        else:
            utility.printMsg("There is no pull request for your current branch. \nStart one using grape review or by "
                             "visiting %s" % ('/'.join([atlassian.url, "projects", args["--project"], "repos",
                                                        args["--repo"], "pull-requests"])))
        return verified

    def testForCleanWorkspace(self, args):
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
                ret = ret and utility.executeSubProcess(cmd.strip(), workingDirectory=os.getcwd()).returncode == 0
        os.chdir(cwd)
        return ret

    def performCustomBuildStep(self, args):
        return self.performCustomStep("build", args)

    def performCustomTestStep(self, args):
        return self.performCustomStep("test", args)

    def performCustomPrePublishSteps(self, args):
        return True

    def tickVersion(self, args):
        ret = True
        if args["--tickVersion"].lower() == "true":
            versionArgs = ["tick"]
            for arg in args["-T"]:
                versionArgs += [arg.strip()]
            ret = grapeMenu.menu().applyMenuChoice("version", versionArgs)
            ret = ret and self.markReviewWithVersionNumber(args)
        return ret

    def performCustomPostPublishSteps(self, args):
        return True

    @staticmethod
    def deleteTopicBranch(args):
        if args["--deleteTopic"].lower == "true":
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

    def publishAllProjects(self, args):
        config = grapeConfig.grapeConfig()
        topic = args["--topic"]

        # make sure public branches are up to date.
        grapeMenu.menu().applyMenuChoice('up', ['up'])

        quiet = not args["-v"]
        # get the outer level public branch destination
        public = args["<public>"]

        # set any CL defined publish policy
        policy = None
        if args["--merge"]:
            policy = "merge"
        if args["--squash"]:
            policy = "squash"
        if args["--rebase"]:
            policy = "rebase"

        # decide whether to recurse into submodules
        recurse = grapeConfig.grapeConfig().get('workspace', 'manageSubmodules')
        if args["--recurse"]:
            recurse = True
        if args["--norecurse"]:
            recurse = False

        # no need to recurse if there are no modified submodules
        submodules = git.getModifiedSubmodules(public, topic)
        recurse = recurse and submodules
        cwd = git.baseDir(quiet=quiet)
        os.chdir(cwd)

        if recurse:
            submapping = config.getMapping('workspace', 'submoduleTopicPrefixMappings')
            submodulePublic = submapping[self.branchPrefix]

            # submodule policy is Command Line requested policy, otherwise is based on 
            #       .grapeconfig.workspace.submodulePublishPolicy
            submodulePolicy = policy
            if not submodulePolicy:
                submodulePolicy = config.getMapping('workspace', 'submodulePublishPolicy')[submodulePublic]
            valid = self.validateInput(submodulePolicy, args)
            proceed = valid and (args["--noverify"] or
                                 utility.userInput("About to publish " + topic + " to "
                                                   + submodulePublic +
                                                   " for the following submodules:\n%s\nProceed? [y/n]" % 
                                                   '\n'.join(submodules), 'y'))
            if proceed:
                for sub in submodules:
                    os.chdir(os.path.join(cwd, sub))

                    grapeMenu.menu().applyMenuChoice('up', ['up', '--public=%s' % submodulePublic])
                    self.publish(submodulePolicy, submodulePublic, topic, args)
            os.chdir(cwd)

        # update policy from config if not set on CL
        if not policy:
            policy = config.getMapping('flow', 'publishPolicy')[public]

        valid = self.validateInput(policy, args)
        proceed = valid and (args["--noverify"] or
                             utility.userInput("About to publish " + topic + " to "+public+" for top level workspace.\n"
                                                                                           "Proceed? [y/n]", 'y'))
        if proceed:
            self.publish(policy, public, topic, args)
            # push subtrees to their respective remote branches
            push_subtrees = config.get("subtrees", 'pushOnPublish').lower() == "true" or args["--pushSubtrees"]
            push_subtrees = push_subtrees and not args["--noPushSubtrees"]
            if push_subtrees:

                subtrees = config.get('subtrees', 'names').strip().split(' ')
                for st in subtrees:
                    st_prefix = config.get('subtree-%s' % st, 'prefix')
                    st_remote = subtree.parseSubtreeRemote(config.get('subtree-%s' % st, 'remote'))
                    st_branchMappings = config.getMapping('subtree-%s' % st, 'topicPrefixMappings')
                    st_branch = st_branchMappings[topic]
                    print("pushing subtree %s to %s (branch %s)..." % (st_prefix, st_remote, st_branch))
                    git.subtree("push --prefix=%s %s %s" % (st_prefix, st_remote, st_branch), quiet=quiet)
        return True
