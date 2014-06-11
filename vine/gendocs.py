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
#Tutorial
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


    """
    def __init__(self):
        self._key= "Tutorial"
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