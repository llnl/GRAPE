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
            f.write("# %s\n" % self._name)
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
maintainer has set you up with grape and wants you to use it for branch creation, library maintainence,
testing stuff before publishing it, doing the correct git incantations to merge branches in a way that
makes sense for your team, etc. The lowly peo--, excuse me, Valued Devleoper view of grape should be:

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
Much of grape also assumes you're working in a clone of a repo, with a remote called 'origin.'
This tutorial assumes you're developing in a project called foo hosted at a stash instance
at https://stash.grape.tutorial.org, and that you're planning to use a two-trunk development model, with both a
`develop` branch and a `master` branch.

### Creating your .grapeconfig file
Ok, lets go to your git repository, and create an initial grape config file.

    cd /path/to/repo
    grape writeConfig .grapeconfig

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
    publicbranches = develop master
    topicprefixmappings = ?:develop
    publishpolicy = ?:merge

The `publicbranches` is a space-delimited list of all of your long-lived public branches. These are typically things
like develop, master, or release, but can be whatever your project thinks makes sense.

The `topicprefixmappings` is a space-delimited list of key:value pairs, where the key is a branch prefix, and the value
is the public branch topic branches with that branch prefix.  For example, if you wanted bugfix  and feature
branches to be branched off of develop and hotfix branches to be branched off of master, you should do the following:

    [flow]
    publicbranches = develop master
    topicprefixmappings = feature:develop bugfix:develop hotfix:master ?:develop
    publishpolicy = ?:merge

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
    publishpolicy = master:squash develop:merge ?:merge

If you don't know what we're talking about here, just leave it as is. Merges are the safest way to go.


###A note for Windows compatibility
If you're on a system where 'git' is not in your path (often true on Windows systems), you'll want to add the following
to a .grapeconfig file in your home directory:

    [git]
    executable = /path/to/your/git/executable/git.exe

where the format of the path is whatever is appropriate for your system. You may need to do this by hand before ever
calling grape.

### Defining your publish process
When your valued developers want to publish their invaluable work to a public branch, your team may have a host of
SQA driven requirements, such as successfull build(s), testing, etc. You'll want to take a look at `grape publish
--help` for more details on this, but for now lets look at a few key things in the `[publish]` section of your
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

`buildcmds` : This is a COMMA -delimited list of commands you use to build your code.
`builddir` : This is the directory where the `buildcmds` are issued from, relative to your repository's base directory.
`testcmds` and `testdir`: Same as `buildcmds` and `builddir`, but for running your project's tests.

Have other custom steps in your process? Make use of prepublish* and postpublish* to customize your process.

If you keep a running change log, you'll want to take a look at the grape publish documentation, paying attention to
updatelog, logskipfirstlines, and logentryheader. If you send email notifications, check out all the documentation
for all the email-related options as well.

If you manage your code reviews using Pull Requests on Stash, and you want to enforce the existence of approved pull
requests for each branch being published, leave `useStash` as True. Otherwise, set it to False.

What about that `tickversion` option? Set it to True if you want to auto-increment your project's version with grape.
Check out `grape version --help` for more info on managing versioning your project with grape.







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