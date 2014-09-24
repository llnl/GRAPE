## Tutorial

## Introducing the `.grapeconfig` file

To write a .grapeconfig file with the settings for grape in your current environment:

    grape writeConfig .grapeconfig

.grapeconfig now contains all of the options various grape commands will use. It's of the following format:

    [SECTION_NAME]
    option = value
    option2 = key:value
    option3 = list:of key:values with:VAL as:a default:value ?:VAL

In the man page for any given grape commands (viewable by typing grape <cmd> --help) , if you see a

    [default = .grapeconfig.SECTION_NAME.option]

this means that that option grabs it's value from the .grapeconfig file for your project by default.

If you're a project maintainer, this .grapeconfig stuff really matters for how you want your team to work.
If you're a lowly peon, err... valued developer, you don't care. You're reading this because your project
maintainer has set you up with grape and wants you to use it for branch creation, library maintenance,
testing stuff before publishing it, doing the correct git incantations to merge branches in a way that
makes sense for your team, etc. The lowly peo--, excuse me, Valued Developer view of grape should be:

    # take a look at available commands
    grape
    # create a new branch
    grape <branchType>
    # <do work>
    gvim foo.txt
    # add a file using git commands
    git add foo.txt
    # inspect the status of your work across all subprojects:
    grape status
    # commit to your local repo all staged changes in all subprojects
    grape commit
    # Update your topic branch with recent changes on the destination public branch
    grape md
    # publish your branch to the appropriate public branch (e.g. master, develop, release, etc)
    grape publish

Any of those grape commands have more options associated with them, which you can inspect by typing

    grape <cmd> --help

And that's all you valued developers need to know! Project maintainers, read on!

## Setting up a project with Grape.
If your project is simple, with a single trunk of development, no submodules or subtrees with third party
libraries, then this section should be all you need. Read on for more advanced topics as they come up.

### Assumptions
This assumes you have a git repository set up, have at least a rudimentary knowledge of git,
you have an idea of how you want to do your branching (single trunk, gitflow, some other weird thing, etc. ),
and you are ready to distribute your well thought-out process using grape.
Much of grape also assumes you're working in a clone of a repo, with a remote called `origin`.
This tutorial assumes you're developing in a project called foo hosted at a stash instance
at https://stash.grape.tutorial.org, and that you're planning to use a two-trunk development model, with both a
`develop` branch and a `master` branch.

### Creating your .grapeconfig file
Ok, let's go to your git repository, and create an initial grape config file.

    cd /path/to/repo
    grape writeConfig .grapeconfig --gitflow

Let's open up that .grapeconfig and edit some config options so that they make sense.

    [repo]
    name = repo_name_not.yet.configured
    url = https://not.yet.configured/scm/project/unknown.git
    httpsbase = https://not.yet.configured
    sshbase = ssh://git@not.yet.configured

For repo.name, put in your project name. Fill out your default url, (either ssh or https), as well as
the https base url and stash url:

    [repo]
    name = foo
    url = https://stash.grape.tutorial.org/scm/foo/foo.git
    httpsbase = https://stash.grape.tutorial.org/scm/
    sshbase = ssh://git@stash.grape.tutorial.org:1111/foo

Take a look at the `[flow]` section. This is probably one of the most important sections in your `.grapeconfig` file,
as it defines your project's branching model.

    [flow]
    publishpolicy = ?:merge master:cascade->develop
    publicbranches = master develop
    topicprefixmappings = hotfix:master bugfix:develop feature:develop ?:develop release:develop
    topicdestinationmappings = release:master

The `publicbranches` is a space-delimited list of all of your long-lived public branches. These are typically things
like develop, master, or release, but can be whatever your project thinks makes sense.

The `topicprefixmappings` determines the start point for your topic branches. It is a space-delimited list of key:value
pairs, where the key is a branch prefix, and the value is the public branch topic branches with that branch prefix.

The ?:develop option means that any branch that isn't named with feature, bugfix, or hotfix as a prefix will be assumed
to branch off of develop.

For each branch type you define in `topicprefixmappings`, grape will dynamically generate a new command for creating
new branches of that type. So, in the above case, `grape feature`, `grape bugfix`, and `grape hotfix` will all be
available as commands.

The publishpolicy is another list, but it maps PUBLIC branches to merge policies. So, if you're on a rebasing kind of
team, choose ?:rebase. If you're a merge kind of team, choose ?:merge. If you want to squash-merge your commits to
master to keep history clean there, but preserve all the churn on develop, do something like the following:

    [flow]
    ...
    publishpolicy = master:cascade->develop develop:merge ?:merge

If you don't know what we're talking about here, just leave it as is. It preserves fine grained history on the develop
branch, but has nice clean history on master.

topicdestinationmappings is similar to topicprefixmappings, but it acts to override where a branch is published to. In
gitflow land, this enables release branches - branches that start in develop (as described in topicprefixmappings) and
get published to master.

###A note for Windows compatibility
If you're on a system where 'git' is not in your path (often true on Windows systems), you'll want to add the following
to a .grapeconfig file in your home directory:

    [git]
    executable = /path/to/your/git/executable/git.exe

where the format of the path is whatever is appropriate for your system. You may need to do this by hand before ever
calling grape.

### Defining your publish process
When your valued developers want to publish their invaluable work to a public branch, your team may have a host of
SQA driven requirements, such as successful build(s), testing, etc. You'll want to take a look at `grape publish
--help` for more details on this, but for now let's look at a few key things in the `[publish]` section of your
.grapeconfig file.

    [publish]
    buildcmds =
    builddir = .
    testcmds =
    testdir = .
    prepublishcmds =
    prepublishdir = .
    postpublishcmds =
    postpublishdir = .
    tickversion = False
    useStash = True
    deletetopic = False
    updatelog = .grapepublishlog
    logskipfirstlines = 0
    logentryheader = <date> <user>
<version>

    emailnotification = False
    emailheader = <public> updated to <version>
    emailserver = smtp.email.server
    emailsendto = user.list@company.com
    emailsubject = <public> updated to <version>

Ok, there's a lot here. But that's because publish can do a lot for you, I promise.

`buildcmds` : This is a COMMA-delimited list of commands you use to build your code.
`builddir` : This is the directory where the `buildcmds` are issued from, relative to your repository's base directory.
`testcmds` and `testdir`: Same as `buildcmds` and `builddir`, but for running your project's tests.

Have other custom steps in your process? Make use of prepublish[cmds|dir] and postpublish[cmds|dir] to customize your
process.

If you keep a running change log, you'll want to take a look at the grape publish documentation, paying attention to
updatelog, logskipfirstlines, and logentryheader. If you send email notifications, check out all the documentation
for all the email-related options as well.

If you manage your code reviews using Pull Requests on Stash, and you want to enforce the existence of approved pull
requests for each branch being published, leave `useStash` as True. Otherwise, set it to False.

What about that `tickversion` option? Set it to True if you want to auto-increment your project's version with grape.
Check out `grape version --help` for more info on managing versioning your project with grape.


## Managing Subprojects with grape
If you'd like to manage third-party library source-code inline with your project, git provides a couple of ways
to do it: Submodules and Subtrees. Googling submodules vs. subtrees will yield discussions as vehemently
idealogical as emacs vs.  vim or git vs. perforce or merge vs rebase.  Grape's philosophy is not to discriminate
based on religion, so it aims to make life easier regardless of your decision, and to hide inherent complexities
associated with both as much as possible. That said, here is our take on situations appropriate for submodules vs
situations more appropriate for subtrees:

### The difference between submodules and subtrees
Google it for details on the technical differences.  Keep in mind as you read forums that a lot of the negative
side effects of both are mitigated by grape, athough the submodule functionality is perhaps more fully flushed
out than the subtree functionality at the current stage of development. That said, the internet probably leans
toward subtrees. In any case, there are still situations where you definitely want one vs. the other, listed
below.

### When to definitely use subtrees
1. When only one or two people on your large team are responsible for library updates, and they can be easily trained on
 the relatively small amount of complexity introduced by subtrees.
2. When, all things being equal, you have lots of team members who are fairly familiar with git and may ignore the
fact that you are using grape. Subtrees tend to 'just work' for plain 'ol git commands, whereas all developers
have to be aware of the fact that they are using submodules if they need access to the submodules.
3. When you have nested subprojects. Subtrees that contain subtrees will work well, submodules that contain submodules
adds complexity that grape doesn't handle at the moment.

### When to definitely use submodules
1. When your subprojects consists of mostly large binary blobs (test baselines, art assets, etc.)
2. When you need to restrict access to a sub-portion of your repository. The restricted files must be in a submodule
to be decoupled enough to restrict access.
3. When you plan to purge history in the subproject on a regular basis. This can be done without a reclone of your
main repository if and only if you are using submodules.

### Grape's assumptions about subprojects
We assume that you're using submodules or subtrees as a means to manage pedigree of your code - when you check out
version 1.2 of your project, you want to make sure you can always build it with the versions of third party libraries
you had when you developed.  We also assume you need to make changes to the third party libs as a regular course of
business (e.g. portability fixes), and that such changes are expected to be reviewed in the context of changes to
your project.

A natural model for this is to have each library be its own repository, either a fork of that library's official git
repo, or a hand rolled one based off of snapshots that your project maintains. Grape assumes that for each of your
public branches in your project, there is a consistently named branch in each of your subprojects. For example,
for your project foo that depends on third party library libBar, foo might have the branches develop and master, and
libBar might have the branches foo_dev and foo_master.

Using this model allows one to merge in updates to the third-party codebase with your changes in a natural way. If
desired, it enables relative easy contributions of your fixes to the library when appropriate.

Currently grape doesn't support recursive subprojects. This doesn't matter too much for subtrees, but for submodules
it might matter a great deal.

## How grape works with submodules
### relevant sections in the `.grapeconfig`

    [workspace]
    subprojecttype = submodule
    managesubmodules = True
    submoduletopicprefixmappings = ?:develop
    submodulepublishpolicy = ?:merge
    submodulepublicmappings = ?:master

`subprojecttype` is used when adding new subprojects, and can be set to either subtree (Default) or submodule.

`managesubmodules` should be set to True to enable grape managed submodules. Otherwise, you're on your own.

`submoduletopicprefixmappings` is analogous to `flow.topicprefixmappings`. When you publish changes in your project,
this is what grape uses to determine which branch in your submodule updated submodules' changes get merged to.

`submodulepublishpolicy` is analagous to 'flow.publishpolicy', but determines what merge rebase action will take
place in your submodules.

`submodulepublicmappings` is a list of key:value pairs that define the association of your project's public branches
to your submodule's public branches, e.g. `develop:foo_dev master:foo_master`.

### branch creation
When you create and checkout a branch in grape using grape <branchType>, branches will be created and checked
out in your submodules as well, using workspace.submodulepublicmappings[flow.topicprefixmappings[<branchType>]] to
determine your submodules' branch's start points.
For example, with  the following `.grapeconfig`:

    [flow]
    topicprefixmappings = bugfix:develop hotfix:master feature:develop ?:develop
    [workspace]
    managesubmodules = True
    submoduletopicprefixmappings = feature:foo_dev bugfix:foo_dev hotfix:foo_master
    submodulepublicmappings = develop:foo_dev master:foo_master

calling `grape bugfix` will create a new branch off of develop in project foo, and a branch of the same name off of
foo_dev in submodule libBar.

### `grape status`
Grape status will gather the status across all submodules and your project. This is different from git status, which
will only give you the status of the repo / submodule you are currently in.

### `grape commit`
Grape commit will commit all changes in submodules first, then perform the commit in the outer level repository to
ensure you have updated the gitlink.

### `grape push`
Grape push pushes changes in your current branch to origin in all submodules and your outer level repository.

### `grape md`
Grape md handles the situation where you're merging in changes to a submodule in a branch that also has changes in
that submodule. This normally is a guaranteed conflict in the gitlink, even if the appropriate merge in the submodule
should be clean. In the above example, while on a branch called feature/user/descr this performs the following steps:
    in foo:
        git merge develop
        on conflict:
            in libBar:
            git merge foo_dev
            on conflict:
                ask user to resolve
            in foo:
            resolve gitlink conflicts
        if still in conflict:
            ask user to resolve
        commit result of merge

Use grape md --continue once you've resolved any conflicts generated by this process.

### `grape publish`
Grape publish will perform the merge actions as defined by workspace.submodulepublishpolicy in all submodules first,
then publish your outer level repo.

### `grape review`
When creating a new pull request with a description, grape will create pull requests in all modified submodules and
append links to those pull requests in your project-level pull request.

### `grape db`
When deleting a branch, grape will delete branches of the same name in your submodules.

## How grape works with subtrees
Grape uses git-subtree, which is part of the contrib/ section of the official git repository. You'll need to install
git-subtree for grape's subtree features to work.

### relevant subtree `.grapeconfig` sections

    [subtrees]
    mergepolicy = nosquash
    pushonpublish = False
    names = libBar

    [subtree-libBar]
    prefix = imports/libBar
    remote = ../libBar
    topicprefixmappings = ?:

### Adding subtrees.
Check out the grape addSubproject --help for more details. When you use addSubproject, grape updates the .grapeconfig
file as appropriate.


### `grape publish`
Grape can be configured to split-push changes in subtrees to their host repository as part of your publish step by
setting subtrees.pushonpublish to True.

# Grape Commands
Below is the most detailed documentation that currently exists for each of the grape commands. You can always look
at a particular commands documentation using grape <cmd> --help.

Some commands are better documented than others, but our use of the docopt.py module guarantees that all available
options are at least listed below.

    
## addSubproject

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

    
## bundle

    grape bundle uses the 'git bundle' feature to extract a subset of history into a git bundle file,
    which can then be sent over a sneakernet to a mirror of your grape project.
    The history range that is extracted is defined in the following way:
        start point:
            for each branch in <list> as defined by --branches, start at the commit tagged by
            <tagprefix>/<branch>.
        end point:
            the tip of each branch in <list> as defined by --branches.
    By default, grape bundle bundles up all active submodules in your repository, according to their
    respective .grapeconfig files.


    Usage:
       grape-bundle [--norecurse] [--branches=<config.patch.branches>]
                    [--tagprefix=<config.patch.tagprefix>]
                    [--describePattern=<config.patch.describePattern>]
                    [--name=<config.repo.name>]
                    [--outfile=<fname>]
                    [--bundleTags=<branchToTagPatternMapping>]


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
       --bundleTags=<mapping>           A list of branch:tagPattern tags to bundle. Note that a broadly defined tag
                                        pattern may yield larger bundle files than you might expect.
                                        [default: .grapeconfig.patch.branchToTagPatternMapping]

    .grapeConfig Defaults:

    [patch]
    branches = master develop
    tagprefix = patched
    describePattern = v*

    [repo]
    name = None


    
## unbundle

    grape unbundle


    Usage:
       grape-unbundle <grapebundlefile>... [--branchMappings=<config.patch.branchMappings>]

    Arguments:
        <grapebundlefile>             The name(s) of the grape bundle file(s) to unbundle.

    Options:
        --branchMappings=<pairlist>   the branch mappings to pass to git fetch to unpack
                                      objects from the bundle file.
                                      [default: .grapeconfig.patch.branchMappings]

    
## status

    Usage: grape-status [-v]

    Options:
    -v      Show git commands being issued. 

    
## checkout

    Usage: grape-checkout [-v] [-b] <branch> 

    Options:
    -v      Show git commands being issued. 
    -b      Create the branch off of the current HEAD in each project.
    

    Arguments:
    <branch>    The name of the branch to checkout. 

    
## push

    grape push pushes your current branch to origin for your outer level repo and all submodules.
    it uses 'git push -u origin HEAD' for the git command.

    Usage: grape-push [--norecurse] [-v]

    Options:
    --norecurse     Don't perform pushes in submodules.  
    -v              Show more git output. 

    
## commit

    Usage: grape-commit [-v] [-m <message>] [-a | <filetree>]  

    Options:
    -m <message>    The commit message.
    -v              Show git commands being issued.
    -a              Commit modified files that have not been staged.
    

    Arguments:
    <filetree> The relative path of files to include in this commit. 

    
## publish

    grape publish
    Merges/Squash-merges/Rebases the current topic branch <type>/<username>/<descr> into the public <branch>,
    where <public> is read from one of the <type>:<public> pairs found in .grapeconfig.flow.topicPrefixMappings,
    .grapeconfig.flow.topicDestinationMappings, and/or .grapeconfig.workspace.submoduleTopicPrefixMappings. The
    branch-dependent publish policy (merge vs. squash merge. vs rebase, etc) is decided using
    grapeconfig.flow.publishPolicy for the top-level repo and the publish policy for
    submodules is decided using grapeconfig.workspace.submodulePublishPolicy.

    Usage:  grape-publish [--squash [--cascade=<branch> ] | --merge |  --rebase]
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
                         [--stashURL=<httpsURL>]
                         [--verifySSL=<bool>]
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
            grape-publish --quick -m <msg> [-v] [--user=<StashUserName>] [--public=<public>] [--noReview]

    Options:
    --squash                Squash merges the topic into the public, then performs a commit if the merge goes clean.
    --cascade=<branch>      For squash merges, can choose to cascade back to <branch> after the merge is
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



    
## clone
 grape-clone
    Clones a git repo and configures it for use with git.

    Usage: grape-clone <url> <path> [--recursive]

    Arguments:
        <url>       The URL of the remote repository
        <path>      The directory where you want to clone the repo to.

    Options:
        --recursive   Recursively clone submodules.
    
## config

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

    
## writeConfig

        grape writeConfig: Writes the current configuration to a file, using any configuration set
        by ~/.grapeconfig or your <REPO_BASE>/.grapeconfig. 

        Usage: 
        grape-writeConfig <file> [--gitflow]

    
## foreach

    Executes a command in each project in this workspace (including the outer level project). 

    Usage: grape-foreach [--quiet] <cmd> 

    Options:
    --quiet      Quiets git's printout of "Entering submodule..."

    Arguments:
    <cmd>        The cmd to execute. 

    
## m

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
        
    
## md

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


    
## mr

    grape mr (merge remote branch)
    Usage: grape-mr [<branch>] [--am | --as | --at | --ay] [-v] [--quiet]

    Arguments:
    <branch>      The name of the remote branch to merge in (without remote/origin or origin/ prefix)
    
    
## db
 Deletes a topic branch both locally and on origin for all projects in this workspace. 
    Usage: grape-db [-D] [<branch>]

    Options:
    -D              Forces the deletion of unmerged branches. If you are on the branch you
                    are trying to delete, this will detach you from the branch and then 
                    delete it, issuing a warning that you are in a detached state.  

    Arguments: 
    <branch>        The branch to delete. Will ask for branch name if not included. 
    
    
    
## cv

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
    
## review

    grape review
    Usage: grape-review [--update | --add]
                        [--title=<title>]
                        [--descr=<file> | -m <description>]
                        [--user=<userName> ]
                        [--reviewers=<userNames>]
                        [--source=<topicBranch>]
                        [--target=<publicBranch>]
                        [--state=<openMergedDeclined>]
                        [--stashURL=<url>]
                        [--verifySSL=<bool>]
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
        --stashURL=<url>            The stash url, e.g. https://rzlc.llnl.gov/stash. 
                                    [default: .grapeconfig.project.stashURL]
        --verifySSL=<bool>          Set to False to ignore SSL certificate verification issues.
                                    [default: .grapeconfig.project.verifySSL]
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



    
## up

    grape up
    Updates the current branch and any public branches. 
    Usage: grape-up [--public=<branch> ] [-v]

    Options:
    --public=<branch>       The public branches to update in addition to the current one,
                            e.g. --public="master develop"
                            [default: .grapeconfig.flow.publicBranches ]
    -v                      Be more verbose.


    
## installHooks
 grape installHooks
    Installs callbacks to grape in .git/hooks, allowing grape-configurable hooks to be used
    in this repo.

    Usage: grape-installHooks [--toInstall=<hook>]...

    Options:
    --toInstall=<hook>    the list of hook-types to install
                          [default: pre-commit pre-push pre-rebase post-commit post-rebase post-merge post-checkout]

    
## runHook
 grape runHook

    Usage: grape-runHook
           grape-runHook pre-commit [--noExit]
           grape-runHook pre-push <dest> <url> [--noExit]
           grape-runHook pre-rebase <basebranch> [<rebasebranch>] [--noExit]
           grape-runHook post-commit [--autopush=<bool>] [--cascade=<pairs>] [--noExit]
           grape-runHook post-rebase [--rebaseSubmodule=<bool>] [--noExit]
           grape-runHook post-merge <wasSquashed> [--mergeSubmodule=<bool>] [--noExit]
           grape-runHook post-checkout <prevHEAD> <newHEAD> <isBranchCheckout> [--checkoutSubmodule=<bool>] [--noExit]

    Options:
        --autopush=<bool>           autopushes commits to origin
                                    [default: .grapeconfig.post-commit.autopush]
        --cascade=<pairs>           performs a post commit cascade
                                    [default: .grapeconfig.post-commit.cascade]
        --rebaseSubmodule=<bool>    [default: .grapeconfig.post-rebase.submoduleUpdate]
        --mergeSubmodule=<bool>     [default: .grapeconfig.post-merge.submoduleUpdate]
        --checkoutSubmodule=<bool>  [default: .grapeconfig.post-checkout.submoduleUpdate
        --noExit                    Normally runhook returns by calling exit(0). With this flag, returns by returning
                                    True.

    Arguments:
        <dest>                      (pre-push only) The destination repo.
        <url>                       (pre-push only) The destination's URL.
        <basebranch>                (pre-rebase only) The upstream commit this branch was forked from.
        <rebasebranch>              (pre-rebase only) The branch being rebased (empty when rebasing current branch)
        <wasSquashed>               (post-merge only) Status flag indicating whether the merge was a squash merge.



    
## uv

    grape uv  - updates your active submodules.
    Usage: grape-uv [-f <sparsefile>] [-v]

    Options:
        
        -f                      Force removal of submodules currently in your view that are taken out of the view as a
                                result to this call to uv. (passes the -f flag to submodule deinit)
        -v                      Be more verbose.

    
## version

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


    
## w
 
    grape w(alkthrough)
    Usage: grape-w [--nogui] [<b1> [<b2>] ] [--] [ <filetree-ish> ]

    Options:
        --nogui         Don't use kompare to do the walkthrough, use whatever diff is your default diff. 

    Optional Arguments:
        <b1>            The first tree to compare
        <b2>            The second tree to compare
        <filetree-ish>  The files to compare.  

    
## q

    grape q
    Quits grape. 

    Usage: grape-q 

    
## internalRelease

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
    --norecurse             Don't create the branch in submodules.
    
    Optional Arguments:
    <descr>                  Single word description of work being done on this branch. Asks by default.


    
## bugfix

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
    --norecurse             Don't create the branch in submodules.
    
    Optional Arguments:
    <descr>                  Single word description of work being done on this branch. Asks by default.


    
## publicRelease

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
    --norecurse             Don't create the branch in submodules.
    
    Optional Arguments:
    <descr>                  Single word description of work being done on this branch. Asks by default.


    
## hotfix

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
    --norecurse             Don't create the branch in submodules.
    
    Optional Arguments:
    <descr>                  Single word description of work being done on this branch. Asks by default.


    
## feature

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
    --norecurse             Don't create the branch in submodules.
    
    Optional Arguments:
    <descr>                  Single word description of work being done on this branch. Asks by default.


    
