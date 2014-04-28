# addSubproject

        grape addSubproject
        Adds a new project to this workspace (such as a new library or a new test suite)

        Usage: grape-addSubproject  --name=<name> --prefix=<prefix> --url=<url> --branch=<branch>
                                    [--subtree [--squash | --nosquash] | --submodule]
                                    [--noverify]
                                    [-v]

        Options:
        --name=<name>       The name of the subproject.
        --prefix=<prefix>   Path to place the subproject in your current workspace. (Relative to the top level
                            directory in your workspace.)
        --url=<url>         The URL (SSH, HTTPS, or Relative URL) of the new project's repository.
        --branch=<branch>   The branch name of the subproject you want to add.
        --subtree           Add this subproject as a subtree. Default behavior if .grapeconfig.workspace.subprojectType
                            is subtree.
        --squash            For subtree projects, if --squash is used, will add <commit> as a squash merge.
                            This defaults to true if .grapeconfig.subtrees.mergePolicy is squash.
        --nosquash          For subtree projects, if --nosquash is used, will ensure full history of <branch> is merged
                            in.
        --submodule         Add this subproject as a submodule. Default behavior if
                            .grapeconfig.workspace.subprojectType is submodule.
        --noverify          Set to prevent grape from asking for user verification before adding the subproject.
        -v                  Set to print all git commands that are issued

    
# bundle

    grape bundle


    Usage:
       grape-bundle [--norecurse] [--branches=<config.patch.branches>]
                    [--tagprefix=<config.patch.tagprefix>]
                    [--describePattern=<config.patch.describePattern>]
                    [--name=<config.repo.name>]
                    [--outfile=<fname>]


    Options:
       --norecurse                      bundle only current level
       --branches=<list>                the space delimited list of branches to bundle.
                                        [default: .grapeconfig.patch.branches]
       --tagprefix=<str>                the prefix used to tag start points to bundle
                                        [default: .grapeconfig.patch.tagprefix]
       --describePattern=<pattern>      passed to git describe to aid in naming the bundle.
                                        [default: .grapeconfig.patch.describePattern]
       --name=<str>                     Name used as a prefix to the bundle file.
                                        [default: .grapeconfig.repo.name]
       --outfile=<fname>                Name of the output bundle file. Default behavior is to
                                        use branch names, the repo name, and output of git-describe
                                        to construct a name. Note that the default file name carrys
                                        semantics for grape unbundle in determining which branches to
                                        update.

    .grapeConfig Defaults:

    [patch]
    branches = master develop
    tagprefix = patched
    describePattern = v*

    [repo]
    name = None


    
# unbundle

    grape unbundle


    Usage:
       grape-unbundle <grapebundlefile> [--branchMappings=<config.patch.branchMappings>]

    Arguments:
        <grapebundlefile>             The name of the grape bundle file to unbundle.

    Options:
        --branchMappings=<pairlist>   the branch mappings to pass to git fetch to unpack
                                      objects from the bundle file.
                                      [default: .grapeconfig.patch.branchMappings]

    
# status

    Usage: grape-status [-v]

    Options:
    -v      Show git commands being issued. 

    
# checkout

    Usage: grape-checkout [-v] [-b] <branch> 

    Options:
    -v      Show git commands being issued. 
    -b      Create the branch off of the current HEAD in each project.
    

    Arguments:
    <branch>    The name of the branch to checkout. 

    
# commit

    Usage: grape-commit [-v] [-m <message>] [-a | <filetree>]  

    Options:
    -m <message>    The commit message.
    -v              Show git commands being issued.
    -a              Commit modified files that have not been staged.
    

    Arguments:
    <filetree> The relative path of files to include in this commit. 

    
# publish

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
                         [--continue]
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
                         [--deleteTopic=<bool>]
                         [--emailNotification=<bool> [--emailHeader=<str> --emailSubject=<str> --emailSendTo=<addr>
                          --emailServer=<smtpserver>]]
                         [<CommitMessageFile>]
            grape-publish --printSteps

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
    --noReview              Don't perform any actions that interact with pull requests.
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

    Optional Arguments:
    <CommitMessageFile>     A file with an update message for this publish command. The pull request associated with
                            this branch will be updated to contain this message. If you don't specify a filename, it is
                            assumed that the contents of the pull request description are intended for the update
                            message. Both the commit message for the merge and an update log will contain this message.
                            Additionally, if email notification is configured, the contents of the email will have
                            this message.

    Publish Steps:
    build :   Runs a custom build step.
    test:
    prePublish:
    tickVersion:
    publish:
    postPublish:
    deleteTopic:



    
# clone
 grape-clone
    Clones a git repo and configures it for use with git.

    Usage: grape-clone <url> <path> [--recursive]

    Arguments:
        <url>       The URL of the remote repository
        <path>      The directory where you want to clone the repo to.

    Options:
        --recursive   Recursively clone submodules.
    
# config

    Configures the current repo to be optimized for GRAPE on LC
    Usage: grape-config [--cv | --nocv] [--nocredcache] [--p4merge] 
                        [--nop4merge] [--p4diff] [--nop4diff] [--git-p4]

    Options:
        --cv            walks you through setting up a sparse checkout for this repo. (interactive)
        --nocv          skips custom-view questions
        --nocredcache   disables https 12 hr credential cacheing (this option recommended for Windows users)
        --p4merge       will set up p4merge as your merge tool. 
        --nop4merge     will skip p4merge questions.
        --p4diff        will set up p4merge as your diff tool. 
        --nop4diff      will skip p4diff questions.
        --git-p4        will configure your repo for use with git-p4 (deprecated)

    
# writeConfig

        grape writeConfig: Writes the current configuration to a file, using any configuration set
        by ~/.grapeconfig or your <REPO_BASE>/.grapeconfig. 

        Usage: 
        grape-writeConfig <file>

    
# foreach

    Executes a command in each project in this workspace (including the outer level project). 

    Usage: grape-foreach [--quiet] <cmd> 

    Options:
    --quiet      Quiets git's printout of "Entering submodule..."

    Arguments:
    <cmd>        The cmd to execute. 

    
# m

    grape m
    merge a local branch into your current branch
    Usage: grape-m [<branch>] [--am | --as | --at | --ay] [--continue] [-v] [--quiet]

    Options:
        --am            Use git's default merge. 
        --as            Do a safe merge - force git to issue conflicts for files that
                        are touched by both branches. 
        --at            Git accept their changes in the event of a conflict (the branch you're merging from)
        --ay            Git will accept your changes in the event of a conflict (the branch you're currently on)
        --continue      Resume your previous merge after resolving conflicts.
        -v              Display git commands.
        --quiet         Don't issue messages if conflicts occur.

    Arguments:
        <branch>        The branch you want to merge in. 
        
    
# md

    grape md  (Merge Down)
    merge changes from a public branch into your current topic branch
    If executed on a public branch, performs a pull --rebase to update your local public branch. 
    Usage: grape-md [--public=<branch>]
                    [--am | --as | --at | --ay]
                    [--continue]
                    [--recurse | --norecurse]
                    [-v]

    Options:
        --public=<branch>       Overrides the public branch to merge from. 
                                Default behavior is to merge according to 
                                .grapeconfig.flow.topicPrefixMappings.
        --am                    Perform the merge using git's default strategy.
        --as                    Perform the merge issuing conflicts on any file modified by both branches.
        --at                    Perform the merge resolving conficts using the public branch's version. 
        --ay                    Perform the merge resolving conflicts using your topic branch's version.
        --recurse               Perform merges in submodules first, then merge in the outer level keeping the
                                results of submodule merges.
        --norecurse             Do not perform merges in submodules, just attempt to merge the gitlinks.
        --continue              Resume the most recent call to grape md that issued conflicts in this workspace.
        -v                      Print out more git commands.


    
# mr

    grape mr (merge remote branch)
    Usage: grape-mr [<branch>] [--am | --as | --at | --ay]

    Arguments:
    <branch>      The name of the remote branch to merge in (without remote/origin or origin/ prefix)
    
    
# db
 Deletes a topic branch both locally and on origin for all projects in this workspace. 
    Usage: grape-db [-D] [<branch>]

    Options:
    -D              Forces the deletion of unmerged branches. If you are on the branch you
                    are trying to delete, this will detach you from the branch and then 
                    delete it, issuing a warning that you are in a detached state.  

    Arguments: 
    <branch>        The branch to delete. Will ask for branch name if not included. 
    
    
    
# cv

    grape cv: create a new custom view
    Usage: grape-cv [--source=<repo>] [--dest=<name>] [--destPath=<path>] [[--noSparse] | [-- <uvargs>...]]  

    Options: 
        --source=<repo>     Path to original clone. 
        --dest=<name>       Name of new workspace. 
        --destPath=<path>   Path (must exist) to place new workspace in. 
                            Full path to workspace will be <path>/<name>
        --noSparse          Skips grape uv, does a vanilla checkout instead. 
    Arguments: 
        <uvargs>            Arguments to pass to grape uv. Note that if you are using the -f
                            option, you should use an absolute path. 
    
# review

    grape review
    Usage: grape-review [--update | --add]
                        [--title=<title>]
                        [--descr=<file> | -m <description>]
                        [--user=<userName> ]
                        [--reviewers=<userNames>]
                        [--source=<topicBranch>]
                        [--target=<publicBranch>]
                        [--state=<openMergedDeclined>]
                        [--project=<prj>]
                        [--repo=<repo>]
                        [--recurse]
                        [-v]
                        [--test]
                        [--prepend | --append]

    Options:
        --update                    Update an existing pull request with a new description, set of reviewers, etc.
                                    This is the default behavior if a pull request already exists for <topicBranch>
                                    targeting <publicBranch>. If --update is set, and an open pull request doesn't
                                    exist, an error will be generated.
        --add                       Add a new pull request. Default behavior if a pull request doesn't exist for
                                    <topicBranch> targeting <publicBranch>. If a pull request already exists and --add
                                    is set, an error will be generated.
        --title=<title>             The pull request`s title.
        --descr=<file>              A file containing the detailed description of work done on <topicBranch>.
        -m <description>            The pull request description.
        --user=<userName>           Your Stash user name.
        --reviewers=<userNames>     A space-separate list of reviewers for <topicBranch>
        --source=<topicBranch>      The branch to review. Defaults to current branch.
        --target=<publicBranch>     The branch to publish <topicBranch> to.
                                    Defaults to .grapeconfig.topicPrefixMappings[topicBranchPrefix].
        --state=<state>             The state of the pull request to update. Valid values are open, merged, and
                                    declined.
                                    [default: open]
        --project=<prj>             The project key part of the stash url, e.g. the "GRP" in
                                    https://rzlc.llnl.gov/stash/projects/GRP/repos/grape/browse.
                                    [default: .grapeconfig.project.name]
        --repo=<repo>               The repo name part of the stash url, e.g. the "grape" in
                                    https://rzlc.llnl.gov/stash/projects/GRP/repos/grape/browse.
                                    [default: .grapeconfig.repo.name]
        --recurse                   If set, adds a pull request for each modified submodule. The pull request for the
                                    outer level repo will have a description with links to the submodules' pull
                                    requests.
        -v                          Be more verbose with git commands.
        --test                      Uses a dummy version of stashy that requires no communication to an actual Stash
                                    server.
        --prepend                   For reviewers, title,  and description updates, prepend <userNames>, <title>,  and
                                    <description> to the existing title / description instead of replacing it.
        --append                    For reviewers, title,  and description updates, append <userNames>, <title>,  and
                                    <description> to the existing title / description instead of replacing it.


    
# up

    grape up
    Updates the current branch and any public branches. 
    Usage: grape-up [--public=<branch> ] [-v]

    Options:
    --public=<branch>       The public branches to update in addition to the current one,
                            e.g. --public="master develop"
                            [default: .grapeconfig.flow.publicBranches ]
    -v                      Be more verbose.


    
# installHooks
 grape installHooks
    Installs callbacks to grape in .git/hooks, allowing grape-configurable hooks to be used
    in this repo.

    Usage: grape-installHooks [--toInstall=<hook>]...

    Options:
    --toInstall=<hook>    the list of hook-types to install
                          [default: pre-commit pre-push pre-rebase post-commit post-rebase post-merge post-checkout]

    
# runHook
 grape runHook

    Usage: grape-runHook
           grape-runHook pre-commit
           grape-runHook pre-push <dest> <url>
           grape-runHook pre-rebase <basebranch> [<rebasebranch>]
           grape-runHook post-commit [--autopush=<bool>] [--cascade=<pairs>]
           grape-runHook post-rebase [--rebaseSubmodule=<bool>]
           grape-runHook post-merge <wasSquashed> [--mergeSubmodule=<bool>]
           grape-runHook post-checkout <prevHEAD> <newHEAD> <isBranchCheckout> [--checkoutSubmodule=<bool>]

    Options:
        --autopush=<bool>           autopushes commits to origin
                                    [default: .grapeconfig.post-commit.autopush]
        --cascade=<pairs>           performs a post commit cascade
                                    [default: .grapeconfig.post-commit.cascade]
        --rebaseSubmodule=<bool>    [default: .grapeconfig.post-rebase.submoduleUpdate]
        --mergeSubmodule=<bool>     [default: .grapeconfig.post-merge.submoduleUpdate]
        --checkoutSubmodule=<bool>  [default: .grapeconfig.post-checkout.submoduleUpdate]

    Arguments:
        <dest>                      (pre-push only) The destination repo.
        <url>                       (pre-push only) The destination's URL.
        <basebranch>                (pre-rebase only) The upstream commit this branch was forked from.
        <rebasebranch>              (pre-rebase only) The branch being rebased (empty when rebasing current branch)
        <wasSquashed>               (post-merge only) Status flag indicating whether the merge was a squash merge.



    
# uv

    grape uv  - updates your sparse-checkout file and optionally performs the sparse checkout. 
    Usage: grape-uv [-f <sparsefile>] [--applyView | --noapplyView]

    Options:
        
        -f <sparsefile>         An existing sparse-checkout file to copy into .git/info. 
                                If this is not defined, grape will walk you through whether you 
                                want each top-level directory. (interactive)
        --applyView             Calls git read-tree -mu HEAD after updating .git/info/sparse-checkout
        --noapplyView           Skips the git read-tree call after updating .git/info/sparse-checkout
                                If neither --applyView nor --noapplyView are specified, grape uv
                                will ask you what you want to do. (interactive)

    
# version

    grape version
    This command is used for projects that wish to have their version numbers managed by grape.

    Usage: grape-version init <version> --file=<path> [--matchTo=<str>] [--prefix=<verPrefix>] [-suffix=<verSuffix>]
                                                      [--tag | --notag | --updateTag=<bool>]
           grape-version tick [--major | --minor | --slot=<int>]
                              [--tag | --notag | --updateTag=<bool>]
                              [--matchTo=<matchTo>]
                              [--prefix=<prefix>] [--suffix=<sufix>] [--tagPrefix=<prefix>] [--file=<path>]
                              [--nocommit]
                              [--notick]

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
        --major             Tick the Major (1st) version number.
        --minor             Tick the Minor (2nd) version number.
        --slot=<int>        Tick the <int>'th version number. 1 = Major, 2 = Minor, 3 = third, etc. If <int> is bigger
                            than the current max number of digits, the version number will be extended to have <int>
                            digits. Default value comes from .grapeconfig.versioning.branchSlotMappings
        --updateTag=<bool>  If true, update the version git annotated tag. [default: .grapeconfig.versioning.updateTag]
        --tag               Forces updateTag to be True.
        --notag             Forces updateTag to be False.
        --tagPrefix=<str>   The prefix for the git version tags. [default: v]
        --tagSuffix=<str>   The suffix for the git version tags. Default value comes from
                            .grapeconfig.versioning.branchTagSuffixMappings.
        --nocommit          Do not create a new commit, just modify <file>. This implies --updateTag=False.
        --notick            Do not tick the version in <file>. Useful with --tag to tag HEAD as being the current
                            version in <file>.


    
# w
 
    grape w(alkthrough)
    Usage: grape-w [--nogui] [<b1> [<b2>] ] [--] [ <filetree-ish> ]

    Options:
        --nogui         Don't use kompare to do the walkthrough, use whatever diff is your default diff. 

    Optional Arguments:
        <b1>            The first tree to compare
        <b2>            The second tree to compare
        <filetree-ish>  The files to compare.  

    
# q

    grape q
    Quits grape. 

    Usage: grape-q 

    
# bugfix

    grape <newtopicbranch>
    Creates a new topic branch <type>/<username>/<descr> off of a public <branch>, where <type> is read from 
    one of the <type>:<branch> pairs found in .grapeconfig.flow.topicPrefixMappings.

    Usage: grape-<type> [--start=<branch>] [--user=<username>] [--noverify] [--recurse | --norecurse] [<descr>] 

    Options:
    --user=<username>       The user developing this branch. Asks by default. 
    --start=<branch>        The start point for this branch. Default comes from .grapeconfig.flow.topicPrefixMappings. 
    --noverify              By default, grape will ask the user to verify the name and start point of the branch. 
                            This disables the verification. 
    --recurse               Create the branch in submodules. 
                            [default: .grapeconfig.workspace.manageSubmodules]
    --norecurse             Don't create teh branch in submodules. 
    
    Optional Arguments:
    <descr>                  Single word description of work being done on this branch. Asks by default.


    
# hotfix

    grape <newtopicbranch>
    Creates a new topic branch <type>/<username>/<descr> off of a public <branch>, where <type> is read from 
    one of the <type>:<branch> pairs found in .grapeconfig.flow.topicPrefixMappings.

    Usage: grape-<type> [--start=<branch>] [--user=<username>] [--noverify] [--recurse | --norecurse] [<descr>] 

    Options:
    --user=<username>       The user developing this branch. Asks by default. 
    --start=<branch>        The start point for this branch. Default comes from .grapeconfig.flow.topicPrefixMappings. 
    --noverify              By default, grape will ask the user to verify the name and start point of the branch. 
                            This disables the verification. 
    --recurse               Create the branch in submodules. 
                            [default: .grapeconfig.workspace.manageSubmodules]
    --norecurse             Don't create teh branch in submodules. 
    
    Optional Arguments:
    <descr>                  Single word description of work being done on this branch. Asks by default.


    
# feature

    grape <newtopicbranch>
    Creates a new topic branch <type>/<username>/<descr> off of a public <branch>, where <type> is read from 
    one of the <type>:<branch> pairs found in .grapeconfig.flow.topicPrefixMappings.

    Usage: grape-<type> [--start=<branch>] [--user=<username>] [--noverify] [--recurse | --norecurse] [<descr>] 

    Options:
    --user=<username>       The user developing this branch. Asks by default. 
    --start=<branch>        The start point for this branch. Default comes from .grapeconfig.flow.topicPrefixMappings. 
    --noverify              By default, grape will ask the user to verify the name and start point of the branch. 
                            This disables the verification. 
    --recurse               Create the branch in submodules. 
                            [default: .grapeconfig.workspace.manageSubmodules]
    --norecurse             Don't create teh branch in submodules. 
    
    Optional Arguments:
    <descr>                  Single word description of work being done on this branch. Asks by default.


    
# rc

    grape <newtopicbranch>
    Creates a new topic branch <type>/<username>/<descr> off of a public <branch>, where <type> is read from 
    one of the <type>:<branch> pairs found in .grapeconfig.flow.topicPrefixMappings.

    Usage: grape-<type> [--start=<branch>] [--user=<username>] [--noverify] [--recurse | --norecurse] [<descr>] 

    Options:
    --user=<username>       The user developing this branch. Asks by default. 
    --start=<branch>        The start point for this branch. Default comes from .grapeconfig.flow.topicPrefixMappings. 
    --noverify              By default, grape will ask the user to verify the name and start point of the branch. 
                            This disables the verification. 
    --recurse               Create the branch in submodules. 
                            [default: .grapeconfig.workspace.manageSubmodules]
    --norecurse             Don't create teh branch in submodules. 
    
    Optional Arguments:
    <descr>                  Single word description of work being done on this branch. Asks by default.


    
