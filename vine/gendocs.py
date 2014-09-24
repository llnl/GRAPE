#!/bin/sh
"exec" "python" "-B" "$0" "$@"

import sys

import grapeMenu
from docopt.docopt import docopt


class Documentation(object):

    def __init__(self, menu):
        super(Documentation, self).__init__()
        self._sections = [Tutorial()]
        for option in menu._options:
            self._sections.append(Section(option))

    @property
    def sections(self):
        return self._sections

    def write(self, f):

        for s in self._sections:
            s.write(f)


class Section(object):
    def __init__(self, option):
        self._name = option._key
        self._text = option.__doc__

    def write(self, f):
        if self._text:
            f.write("## %s\n" % self._name)
            f.write(self._text)
            f.write("\n")


class Tutorial(Section):
    """
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
    logentryheader = <date> <user>\n<version>\n
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

    """
    def __init__(self):
        self._key = "Tutorial"
        self._text = Tutorial.__doc__
        super(Tutorial, self).__init__(self)


def main(fname):
    """
    dumps documentation to a file.

    Usage:  gendocs.py <fname>

    Arguments:
    <fname>     The file to write documentation to.

    """
    doc = Documentation(grapeMenu.menu())
    with open(fname, 'w') as f:
        doc.write(f)

if __name__ == "__main__":
    args = docopt(main.__doc__, argv=sys.argv[1:])
    main(args["<fname>"])
    sys.exit(0)
