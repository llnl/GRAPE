import logging
import os
import threading
from vine import grape_errors
from vine import config_parser_global
from vine import config_parser_user
from vine import grapeGit as git
from vine import vine_logging
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.option import Option

try:
    import tkinter as Tk
    from tkinter import font
    TkinterImportError = None
except ImportError as e:
    TkinterImportError = e


class Walkthrough(Option, WorkspaceDirHandler):
    """
    grape w(alkthrough)
    Usage: grape-w [--difftool=<tool>] [--height=<height>] [--width=<width>] [--fontSize=<font_size>] 
                   [--showUnchanged] [--noFetch] [--mergeDiff | --rawDiff ]
                   [--noInactive] [--noTopLevel] [--noSubmodules] [--noSubtrees] [--noNestedSubprojects]
                   [<b1>] [--staged | --workspace | <b2>]

    Options:
        --difftool=<tool>           Command to use for diff.
                                    Valid choices are: kdiff3, kompare, tkdiff,
                                       meld, xxdiff, emerge, gvimdiff,
                                       ecmerge, diffuse, opendiff, p4merge, and araxis.
                                    If unspecified, default git difftool will be used.
        --height=<height>           Height of window in pixels.
                                    [default: .grapeconfig.walkthrough.height]
        --width=<width>             Width of window in pixels.
                                    [default: .grapeconfig.walkthrough.width]
        --fontSize=<font_size>      Initial font size to use for graphical user interface.
        --staged                    Compare staged changes with branch <b1>.
        --workspace                 Compare workspace files with branch <b1>.
        --mergeDiff                 Perform diff of branches from common ancestor (diff <b1>...<b2>) (default).
        --rawDiff                   Perform raw diff of branch files (diff <b1> <b2>).
        --showUnchanged             Show unchanged subprojects.
        --noFetch                   Do not fetch.
        --noInactive                Do not show inactive subprojects.
        --noTopLevel                Do not show outer level project.
        --noSubmodules              Do not show submodules.
        --noSubtrees                Do not show nested subtrees.
        --noNestedSubprojects       Do not show nested subprojects.
        <b1>                        The first branch to compare.
                                    Defaults to the current branch of workspace.
        <b2>                        The second branch to compare.
                                    Defaults to the public branch for <b1>.

    """
    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_WALKTHROUGH)
        config.set(self.SECTION_WALKTHROUGH, 'height', '400')
        config.set(self.SECTION_WALKTHROUGH, 'width', '800')
        config.set(self.SECTION_WALKTHROUGH, 'difftool', 'xxdiff')

    def __init__(self):
        super(Walkthrough, self).__init__()
        self._key = "w"
        self._section = "Code Reviews"

    def description(self):
        return "Walk through diffs between branches"

    @vine_logging.log_wrapper
    def execute(self,args):
        if TkinterImportError:
            logging.error("grape w requires Tkinter.\n  The following error was raised during the import:\n\n%s\n" % TkinterImportError)
            return True
        config = config_parser_global.grapeConfig()
        difftool = args["--difftool"]
        height = args["--height"]
        width = args["--width"]
        doMergeDiff = True
        if args["--rawDiff"]:
            doMergeDiff = False
        elif args["--mergeDiff"]:
            # This is already the default
            doMergeDiff = True

        b1 = args["<b1>"]
        if not b1:
            b1 = git.currentBranch(execution_path=self.workspace_dir)

        b2 = args["<b2>"]

        if args["--staged"]:
            b2 = b1
            b1 = "--cached"
            doMergeDiff = False
        elif args["--workspace"]:
            b2 = "--"
            doMergeDiff = False
        else:
            if not b2:
                try:
                    # put the public branch first so merge diff shows
                    # changes on the current branch.
                    b2 = b1
                    b1 = config.getPublicBranchFor(b2)
                except:
                    b2 = ""
                    doMergeDiff = False

        diffargs = ""

        root = Tk.Tk()
        root.title("GRAPE walkthrough")

        DiffManager(master=root, height=height, width=width, fontsize=args["--fontSize"],
                    branchA=b1, branchB=b2,
                    difftool=difftool, diffargs=diffargs,
                    doMergeDiff=doMergeDiff,
                    showUnchanged=args["--showUnchanged"],
                    showInactive=not args["--noInactive"],
                    showToplevel=not args["--noTopLevel"],
                    showSubmodules=not args["--noSubmodules"],
                    showSubtrees=not args["--noSubtrees"],
                    showNestedSubprojects=not args["--noNestedSubprojects"],
                    noFetch=args["--noFetch"],
                    workspace_dir=self.workspace_dir)

        root.mainloop()

        try:
            root.destroy()
        except:
            pass
        return True

# Base class for navigating files in a workspace
class ProjectManager(WorkspaceDirHandler):
    def __init__(self, master, *, workspace_dir, **kwargs):
        super(ProjectManager, self).__init__()
        self.workspace_dir = workspace_dir
        height = kwargs.get('height', 0)
        width  = kwargs.get('width', 0)

        fontsize = kwargs.get('fontsize', 0)

        default_font = font.nametofont("TkDefaultFont").actual()
        if fontsize:
            self.fontsize = int(fontsize)
        else:
            #self.fontsize = int(default_font["size"])
            self.fontsize = 12

        self.fontfamily = default_font["family"]

        self.master = master
        self.grapeconfig = config_parser_global.grapeConfig()
        self.oldprojindex = 0
        self.showInactive          = kwargs.get('showInactive', True)
        self.showToplevel          = kwargs.get('showToplevel', True)
        self.showSubmodules        = kwargs.get('showSubmodules', True)
        self.showSubtrees          = kwargs.get('showSubtrees', True)
        self.showNestedSubprojects = kwargs.get('showNestedSubprojects', True)

        # Colors
        self.fginit     = kwargs.get('fginit', 'black')
        self.bginit     = kwargs.get('bginit', 'gray')
        self.fgvisited  = kwargs.get('fgvisited', 'slate gray')
        self.bgvisited  = kwargs.get('bgvisited', 'light gray')
        self.fgselected = kwargs.get('fgselected', 'black')
        self.bgselected = kwargs.get('bgselected', 'goldenrod')
        self.fgactive   = kwargs.get('fgactive', 'black')
        self.bgactive   = kwargs.get('bgactive', 'light goldenrod')

        self.resizable = []

        # Panel labels
        # These variables should be set by derived classes
        self.filepanelabel = Tk.StringVar()
        self.projpanelabel = Tk.StringVar()

        # Main resizable window
        self.main = Tk.PanedWindow(master, height=height, width=width, sashwidth=4)

        # Create file navigation pane widgets
        self.filepanel = Tk.Frame()
        self.filelabel = Tk.Label(self.filepanel, textvariable=self.filepanelabel)
        self.makeResizable(self.filelabel)
        self.filescroll = Tk.Scrollbar(self.filepanel, width=10)
        self.filelist = Tk.Listbox(self.filepanel, background=self.bginit, foreground=self.fginit, selectbackground=self.bgselected, selectforeground=self.fgselected, yscrollcommand=self.filescroll.set, selectmode=Tk.SINGLE)
        self.makeResizable(self.filelist)
        self.filescroll.config(command=self.filelist.yview)
        self.filelist.bind("<Double-Button-1>", lambda e: self.spawnDiff())

        # Place file navigation pane widgets
        self.filelabel.pack(side=Tk.TOP, fill=Tk.X)
        self.filescroll.pack(side=Tk.RIGHT, fill=Tk.Y)
        self.filelist.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=1)
        self.filepanel.pack(fill=Tk.BOTH, expand=1)

        # Create subproject navigation widgets
        self.projpanel = Tk.Frame()
        self.projlabel = Tk.Label(self.projpanel, textvariable=self.projpanelabel)
        self.makeResizable(self.projlabel)
        self.projscroll = Tk.Scrollbar(self.projpanel, width=10)
        self.projlist = Tk.Listbox(self.projpanel, background=self.bginit, foreground=self.fginit, selectbackground=self.bgselected, selectforeground=self.fgselected, yscrollcommand=self.projscroll.set, selectmode=Tk.SINGLE)
        self.makeResizable(self.projlist)
        self.projscroll.config(command=self.projlist.yview)
        self.projlist.bind("<Double-Button-1>", lambda e: self.chooseProject())

        # Place subproject navigation widgets
        self.projscroll.pack(side=Tk.LEFT, fill=Tk.Y)
        self.projlabel.pack(side=Tk.TOP, fill=Tk.X)
        self.projlist.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=1)
        self.projpanel.pack(fill=Tk.BOTH, expand=1)

        # Populate subproject navigation list
        logging.info("Populating projects list...")

        self.projects = []
        self.projtype = []

        # Outer level repo
        if self.showToplevel:
            self.projects.append("")
            self.append_project_data(
                list_item="? <Outer Level Project>",
                type_="Outer")

        # Nested subprojects
        self.subprojects = []
        if self.showNestedSubprojects:
            activeNestedSubprojects = (config_parser_user.getAllActiveNestedSubprojectPrefixes(workspaceDir=self.workspace_dir))
            self.projects.extend(activeNestedSubprojects)
            self.subprojects.extend(activeNestedSubprojects)
            for proj in activeNestedSubprojects:
                self.append_project_data(
                    list_item=f"? {proj} <Nested Subproject>",
                    type_="Active Nested")
            if self.showInactive:
                inactiveNestedSubprojects = list(set(config_parser_global.grapeConfig().getAllNestedSubprojects())
                    - set(config_parser_user.getAllActiveNestedSubprojects(workspaceDir=self.workspace_dir)))
                self.projects.extend(inactiveNestedSubprojects)
                self.subprojects.extend(inactiveNestedSubprojects)
                for proj in inactiveNestedSubprojects:
                    self.append_project_data(
                        list_item=f"? {proj} <Inactive Nested Subproject>",
                        type_="Inactive Nested")

        # Submodules
        self.submodules = []
        if self.showSubmodules:
            activeSubmodules = (git.getActiveSubmodules(execution_path=self.workspace_dir))
            self.projects.extend(activeSubmodules)
            self.submodules.extend(activeSubmodules)
            for proj in activeSubmodules:
                self.append_project_data(
                    list_item=f"? {proj} <Submodule>",
                    type_="Submodule")
            if self.showInactive:
                inactiveSubmodules = list(set(git.getAllSubmodules(execution_path=self.workspace_dir)) - set(git.getActiveSubmodules(execution_path=self.workspace_dir)))
                self.projects.extend(inactiveSubmodules)
                self.submodules.extend(inactiveSubmodules)
                for proj in inactiveSubmodules:
                    self.append_project_data(
                        list_item=f"? {proj} <Inactive Submodule>",
                        type_="Inactive Submodule")

        # Subtrees
        self.subtrees = []
        if self.showSubtrees:
            self.subtrees = [self.grapeconfig.get(f'subtree-{proj}', 'prefix') for proj in self.grapeconfig.get(Option.SECTION_SUBTREES, 'names').strip().split()]
            self.projects.extend(self.subtrees)
            for proj in self.subtrees:
                self.append_project_data(
                    list_item=f"? {proj} <Subtree>",
                    type_="Subtree")

        logging.info("Done.")

        # Resize the project pane based on its contents
        self.projlistwidth = 0
        self.numprojects = 0
        for proj in self.projlist.get(0, Tk.END):
            if len(proj) > self.projlistwidth:
                self.projlistwidth = len(proj)
            self.numprojects += 1
        self.projlist.config(width=self.projlistwidth)

        # Place the panes in the main window
        self.main.add(self.projpanel)
        self.main.add(self.filepanel)
        self.main.pack(fill=Tk.BOTH, expand=1, side=Tk.BOTTOM)

    def append_project_data(self, *, list_item, type_):
        self.projlist.insert(Tk.END, list_item)
        self.projtype.append(type_)

    def chooseProject(self):
        oldlabel = self.projpanelabel.get()
        self.projpanelabel.set("Working...")
        self.master.update()
        index = self.projlist.index(Tk.ACTIVE)
        self.projlist.itemconfig(self.oldprojindex, bg=self.bgvisited, fg=self.fgvisited)
        try:
            self.initFiles(index)
            self.projlist.itemconfig(index, bg=self.bgactive, fg=self.fgactive)
            self.oldprojindex = index
        except:
            pass
        self.projpanelabel.set(oldlabel)
        self.master.update()

    def makeResizable(self, widget):
        widget.config(font=(self.fontfamily, self.fontsize))
        self.resizable.append(widget)

    def changeFont(self, *args):
        self.fontsize = self.fontselection.get()
        for label in self.resizable:
            label.config(font=(self.fontfamily, self.fontsize))

    def get_selected_project_name(self):
        index = self.projlist.index(Tk.ACTIVE)
        project_name, _ = self.projlist.get(index).split("<")
        name_split = project_name.split()
        if len(name_split) < 2:
            return ""
        # name_split[1] is the project name, name_split[0] is status
        return name_split[1]

    def spawnDiff(self):
        index = self.filelist.index(Tk.ANCHOR)
        try:
            file = self.filenames[index]
            if file != "":
                project_name = self.get_selected_project_name()
                file_abs_path = os.path.join(self.workspace_dir,
                                             project_name,
                                             file)
                if not os.path.exists(file_abs_path):
                    logging.warning(f"Diff file {file_abs_path} not found.")

                t = threading.Thread(target=self.execute,
                                     kwargs={'file_': file_abs_path})
                t.start()
                self.filelist.itemconfig(index, bg=self.bgvisited, fg=self.fgvisited)
        except:
            pass

    def setProjectStatus(self, index, status):
        oldString = self.projlist.get(index)
        newString = status + oldString[1:]
        self.projlist.delete(index)
        self.projlist.insert(index, newString)

    def removeProjectEntry(self, index):
        del self.projects[index]
        self.projlist.delete(index)
        del self.projtype[index]

    # This should be implemented by derived classes
    def initFiles(self, index):
        pass

    # This should be implemented by derived classes
    def execute(self, file_):
        pass

class DiffManager(ProjectManager):
    def __init__(self, master, *, workspace_dir, **kwargs):
        validDiffTools = [ 'kdiff3', 'kompare', 'tkdiff', 'meld', 'xxdiff', 'emerge', 'gvimdiff', 'ecmerge', 'diffuse', 'opendiff', 'p4merge', 'araxis' ]

        # Configurable parameters
        difftool = kwargs.get('difftool', None)
        if difftool is None:
            try:
                difftool = git.config("--get diff.tool", execution_path=workspace_dir)
            except:
                pass

            if difftool == "vimdiff":
                logging.info("Using gvimdiff instead of vimdiff.")
                difftool = "gvimdiff"

        if difftool not in validDiffTools:
            logging.info("Using default difftool.")
            self.difftool = "default difftool"
            self.difftoolarg = ""
        else:
            self.difftool = difftool
            self.difftoolarg = f"-t {difftool}"

        self.diffargs = kwargs.get('diffargs', "")
        self.noFetch = kwargs.get('noFetch', False)
        self.branchA = self.getBranch(kwargs.get('branchA', ""),
                                      workspace_dir=workspace_dir)
        self.branchB = self.getBranch(kwargs.get('branchB', ""),
                                      workspace_dir=workspace_dir)
        self.diffbranchA = ""
        self.diffAnnotationA = Tk.StringVar()
        self.diffAnnotationA.set(self.branchA)
        self.diffbranchB = ""
        self.diffAnnotationB = Tk.StringVar()
        self.diffAnnotationB.set(self.branchB)
        self.showUnchanged = kwargs.get('showUnchanged', False)
        self.doMergeDiff = kwargs.get('doMergeDiff', True)

        super(DiffManager, self).__init__(master, workspace_dir=workspace_dir,
                                          **kwargs)

        # Branch specification pane
        self.branchpane = Tk.Frame(master)
        self.branchlabelA= Tk.Label(self.branchpane, text="Branch A:")
        self.makeResizable(self.branchlabelA)
        self.branchnameA= Tk.Label(self.branchpane, textvariable=self.diffAnnotationA)
        self.makeResizable(self.branchnameA)
        self.branchlabelB= Tk.Label(self.branchpane, text="Branch B:")
        self.makeResizable(self.branchlabelB)
        self.branchnameB= Tk.Label(self.branchpane, textvariable=self.diffAnnotationB)
        self.makeResizable(self.branchnameB)

        # Create font size selector
        fontpanel = Tk.Frame(master)
        fontlabel = Tk.Label(fontpanel, text="Font size")
        self.makeResizable(fontlabel)
        fontlabel.pack(side=Tk.LEFT)
        fontoptions = [self.fontsize]
        for i in range(1, int(self.fontsize/2)-1):
            fontoptions.insert(0, self.fontsize - 2*i)
            fontoptions.append(self.fontsize + 2*i)
        self.fontselection = Tk.StringVar(master=master)
        self.fontselection.set(self.fontsize)
        self.fontselection.trace("w", self.changeFont)
        fontselect = Tk.OptionMenu(fontpanel, self.fontselection, *fontoptions)
        self.makeResizable(fontselect)
        # make drop down entries resizable
        self.makeResizable(fontpanel.nametowidget(fontselect.menuname))
        fontselect.pack(side=Tk.LEFT)
        fontpanel.pack(side=Tk.LEFT, anchor=Tk.NW,)

        self.branchlabelA.pack(side=Tk.LEFT, fill=Tk.Y)
        self.branchnameA.pack(side=Tk.LEFT, fill=Tk.Y)
        self.branchlabelB.pack(side=Tk.LEFT, fill=Tk.Y)
        self.branchnameB.pack(side=Tk.LEFT, fill=Tk.Y)
        self.branchpane.pack(side=Tk.TOP)


        # If we are diffing against the workspace, get the status of the workspace
        # and save the set of changed files in the outer project (including submodules).
        changedFiles = None

        if self.showToplevel or len(self.submodules) > 0:
            logging.info("Gathering status in outer level project...")
            changedFiles = git.diff(f"--name-only {self.diffBranchSpec(self.branchA, self.branchB)}",
                                    execution_path=self.workspace_dir).split()
            logging.info("Done.")

        # Get the url mapping for all submodules
        if len(self.submodules) > 0:
            git.getAllSubmoduleURLMap(execution_path=self.workspace_dir)

        logging.info("Examining projects...")

        # Loop over list backwards so we can delete entries
        for index in reversed(range(self.numprojects)):
            dir_ = self.projects[index]
            type_ = self.projtype[index]
            haveDiff = False
            if type_ == "Outer":
                # Outer is always last in the reverse iteration,
                # so all submodule entries should have already been removed.
                haveDiff = len(changedFiles) > 0
            elif type_.endswith("Submodule"):
                if not type_.startswith("Inactive") or self.showInactive:
                    if dir_ in changedFiles:
                        haveDiff = True
                        changedFiles.remove(dir_)
            elif type_.endswith("Nested"):
                if type_.startswith("Inactive"):
                    # It might not be worth the time to check for differences in inactive subprojects
                    #TODO
                    pass
                else:
                    project_dir = os.path.join(self.workspace_dir, dir_)
                    logging.info(f"Gathering status in {dir_}...")
                    try:
                        haveDiff = len(git.diff(f"--name-only {self.diffBranchSpec(self.branchA, self.branchB)}", execution_path=project_dir).split()) > 0
                    except grape_errors.GrapeGitError as e:
                        if "unknown revision or path not in the working tree" in e.gitOutput.lower():
                            branches = self.diffBranchSpec(self.branchA, self.branchB)
                            logging.info(f"Could not diff {branches}. " +
                                         " Branch may not exist in {dir_}.")
                        else:
                            raise
                        haveDiff = False
                    logging.info("Done.")
            elif type_.endswith("Subtree"):
                nestedFiles = git.diff(f"--name-only {self.diffBranchSpec(self.branchA, self.branchB)} {dir_}", execution_path=self.workspace_dir).split()
                if len(nestedFiles) > 0:
                    haveDiff = True
                    for changedFile in changedFiles:
                        if changedFile.startswith(dir_ + os.path.sep):
                            changedFiles.remove(changedFile)

            if haveDiff:
                self.setProjectStatus(index, "*")
            elif self.showUnchanged:
                self.setProjectStatus(index, " ")
            else:
                self.removeProjectEntry(index)

        logging.info("Done.")

        self.filepanelabel.set(f"Double click to launch {self.difftool}")
        if len(self.projects) > 0:
            self.projpanelabel.set("Double click to choose a project")
        else:
            self.projpanelabel.set("No differences")

    def diffBranchSpec(self, branchA, branchB):
        if self.doMergeDiff:
            return f"{branchA}...{branchB}"
        return f"{branchA} {branchB}"

    def getBranch(self, branch, workspace_dir=None):
        # workspace_dir manually set only before DiffManager' super() call.
        if not workspace_dir:
            workspace_dir = self.workspace_dir
        if not branch.startswith("--"):
            try:
                git.shortSHA(branch, execution_path=workspace_dir)
            except:
                if not branch.startswith("origin/"):
                    branch = git.join_list_as_git_path(["origin", branch])
            # TODO figure out what to do with SHA's in user input
            # TODO always fetch the origin before diffing?
            # TODO figure out ahead behind (git rev-list --left-right --count develop...develop)
            if not self.noFetch and branch.startswith("origin/"):
                git.fetch("origin", branch.partition("/")[2], execution_path=workspace_dir)
        return branch

    def getSubBranch(self, branch):
        submapping = self.grapeconfig.getMapping(Option.SECTION_WORKSPACE, 'submodulepublicmappings')
        if not branch.startswith("--"):
            branchParts = branch.split("/",1)
            if len(branchParts) == 1 or branchParts[0] == "origin":
                if branchParts[-1] in submapping.keys():
                    branchParts[-1] = submapping[branchParts[-1]]
            if not isinstance(branchParts, list):
                branchParts = [branchParts]
            return git.join_list_as_git_path(branchParts)
        return branch

    def initFiles(self, index):
        self.filelist.delete(0,Tk.END)
        dir_ = self.projects[index]
        type_ = self.projtype[index]

        self.diffbranchA = self.branchA
        self.diffbranchB = self.branchB

        if type_.endswith("Submodule"):
            self.diffbranchA = self.getSubBranch(self.branchA)
            self.diffbranchB = self.getSubBranch(self.branchB)

        if type_.startswith("Inactive"):
            git.gitcmd("ls-remote", execution_path=self.workspace_dir)
            self.filelist.insert(Tk.END, "<Unable to diff>")
            self.filenames.append("")
        else:
            # TODO handle non-existent branches on subprojects
            tmp_work_directory = os.path.join(self.workspace_dir, dir_)
            with self.temp_work_in_dir(tmp_work_directory):
                self.diffbranchA = self.getBranch(self.diffbranchA)
                self.diffbranchB = self.getBranch(self.diffbranchB)
                self.filenames = []
                diffoutput = git.diff(f"--name-status --find-renames --find-copies {self.diffargs} {self.diffBranchSpec(self.diffbranchA, self.diffbranchB)} .", execution_path=self.workspace_dir).splitlines()
            statusdict = { "A":"<Only in B>",
                           "C":"<File copied>",
                           "D":"<Only in A>",
                           "M":"",
                           "R":"<File renamed>",
                           "T":"<File type changed>",
                           "U":"<File unmerged>",
                           "X":"<Unknown status>" }

            if len(diffoutput) > 0:
                for line in diffoutput:
                    [status, file] = line.split(None, 1)
                    statusstring = statusdict[status[0]]
                    if status[0] == 'R' or status[0] == 'C':
                        files = file.split(None,1)
                        if status[1:] == '100':
                            filename = ""
                        else:
                            statusstring += "*"
                        filename = files
                        filedisplay = " -> ".join(files)
                    else:
                        filedisplay = file
                        filename = file
                    if type_ == "Outer":
                        if filename in self.submodules:
                            continue
                        inSubtree = False
                        for subtree in self.subtrees:
                            if filename.startswith(subtree+os.path.sep):
                                inSubtree = True
                                break
                        if inSubtree:
                            continue

                    self.filelist.insert(Tk.END, f"{filedisplay} {statusstring}")
                    self.filenames.append(filename)
            if len(self.filelist) == 0:
                self.filelist.insert(Tk.END, "<No differences>")
                self.filenames.append("")

        if self.branchA == "--cached":
            self.diffAnnotationA.set(f"{self.diffbranchB} <cached>")
            self.diffAnnotationB.set("<staged>")
        elif self.branchB == "--":
            self.diffAnnotationA.set(self.diffbranchA)
            self.diffAnnotationB.set("<workspace>")
        else:
            self.diffAnnotationA.set(self.diffbranchA)
            self.diffAnnotationB.set(self.diffbranchB)


    def execute(self, file_):
        try:
            cmd = f"difftool --find-renames --find-copies  {self.difftoolarg} -y {self.diffargs} {self.diffBranchSpec(self.diffbranchA, self.diffbranchB)} -- "
            if isinstance(file_, list):
                cmd += f"\"{file_[0]}\" \"{file_[1]}\""
            else:
                cmd += f"\"{file_}\""
            # Git command executed from same path as diffed file.
            execution_path = os.path.dirname(file_)
            git.gitcmd(cmd, "Failed to launch difftool",
                       execution_path=execution_path)
        except grape_errors.GrapeGitError as e:
            logging.error(f"{e.message} (return code {e.code})\n{e.gitOutput}")
