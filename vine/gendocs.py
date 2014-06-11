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
## Getting Started
If your project is simple, with a single trunk of development, no submodules or subtrees with third party
libraries, then this section should be all you need. Read on for more advanced topics as they come up.

To write a .grapeconfig file with the settings for grape in your current environment:
    grape writeConfig .grapeconfig

.grapeconfig now contains all of the options various grape commands will use. It's of the following format:
    [SECTION_NAME]
    option = value
    option2 = key:value
    option3 = list:of key:values with:VAL as:a default:value ?:VAL

In the man page for any given grape commands (viewable by typing grape <cmd> --help) , if you see a
        [default = .grapeconfig.SECTION_NAME.option]
this meansthat that option grabs it's value from the .grapeconfig file for your project by default.

If you're a project maintainer, this .grapeconfig stuff really matters for how you want your team to work.
If you're a lowly peon, err... valued developer, you don't care. You're reading this because your project
maintainer has set you up with grape and wants you to use it for branch creation, library maintainence,
testing stuff before publishing it, doing the correct git incantations to merge branches in a way that
makes sense for your team, etc. The lowly peo--, excuse me, Valued Devleoper view of grape should be:
    # create a new branch
    grape <branchType>
    <do work>
    grape status
    grape commit
    grape publish




    """
    def __init__(self):
        option = {}
        option._name = "Tutorial"
        option._text = Tutorial.__doc__
        super(Tutorial, self).__init__(option)


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