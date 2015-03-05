import sys,os,tempfile
import option
import grapeConfig
import grapeGit as git
import utility
import threading
import Tkinter as Tk

class Walkthrough(option.Option):
    """ 
    grape w(alkthrough)
    Usage: grape-w [--difftool=<tool>] [--height=<height>] [--width=<width>] [<b1>] [<b2>]

    Options:
        --difftool=<tool>  Command to use for diff.
                           Valid choices are: kdiff3, kompare, tkdiff,
                              meld, xxdiff, emerge, vimdiff, gvimdiff,
                              ecmerge, diffuse, opendiff, p4merge, and araxis.
                           [default: .grapeconfig.walkthrough.difftool]
        --height=<height>  Height of window in pixels.
                           [default: .grapeconfig.walkthrough.height]
        --width=<width>    Width of window in pixels.
                           [default: .grapeconfig.walkthrough.width]
        <b1>               The first branch to compare.
                           Defaults to the current branch of workspace.
        <b2>               The second branch to compare
                           Defaults to the public branch for <b1>.

    """
    def setDefaultConfig(self, config):
        config.ensureSection("walkthrough")
        config.set('walkthrough', 'height', '400')
        config.set('walkthrough', 'width', '800')
        config.set('walkthrough', 'difftool', 'xxdiff')

    def __init__(self):
        super(Walkthrough, self).__init__()
        self._key = "w"
        self._section = "Code Reviews"

    def description(self):
        return "Walk through diffs between branches"

    def execute(self,args):
        config = grapeConfig.grapeConfig()
        difftool = args["--difftool"]
        height = args["--height"]
        width = args["--width"]

        cwd = os.getcwd()
        os.chdir(utility.workspaceDir())

        b1 = args["<b1>"] 
        if not b1: 
            b1 = git.currentBranch()
        b2 = args["<b2>"]
        if not b2: 
           try:
              b2 = config.getPublicBranchFor(b1)
           except:
              b2 = ""

        diffargs = ""
               
        # make sure our remote references are up to date if we're
        # comparing with something in the origin repo
        if 'origin' in b1:
            try: 
                git.fetch("origin", b1)
            except:
                pass

        if 'origin' in b2:
            try: 
                git.fetch("origin", b2)
            except:
                pass

        root = Tk.Tk()
        root.title("GRAPE walkthrough")
        
        diffmanager = DiffManager(root, height, width, b1, b2, difftool, diffargs)
        
        root.mainloop()
        
        os.chdir(cwd)

        try:
           root.destroy()
        except:
           pass
        return True


bginit = 'gray'
fginit = 'black'
bgdone = 'light gray'
fgdone = 'slate gray'
bgactive = 'light goldenrod'
fgactive = 'black'
bgselected = 'goldenrod'
fgselected = 'black'

class DiffManager:
   def __init__(self, master, height, width, branchA, branchB, difftool, diffargs):
      self.master = master
      self.grapeconfig = grapeConfig.grapeConfig()
      self.oldprojindex = 0
      # Configurable parameters
      self.difftool = difftool
      self.branchA = branchA
      self.branchB = branchB
      self.diffargs = diffargs

      # Main resizable window
      self.main = Tk.PanedWindow(master, height=height, width=width, sashwidth=4)
      # Create file navigation pane widgets
      self.filepanel = Tk.Frame()
      self.filelabel = Tk.Label(self.filepanel, text="Double click to launch %s" % self.difftool)
      self.filescroll = Tk.Scrollbar(self.filepanel, width=10)
      self.filelist = Tk.Listbox(self.filepanel, background=bginit, foreground=fginit, selectbackground=bgselected, selectforeground=fgselected, yscrollcommand=self.filescroll.set, selectmode=Tk.SINGLE)
      self.filescroll.config(command=self.filelist.yview)
      self.filelist.bind("<Double-Button-1>", lambda e: self.spawnDiff())

      # Place file navigation pane widgets
      self.filelabel.pack(side=Tk.TOP, fill=Tk.X)
      self.filescroll.pack(side=Tk.RIGHT, fill=Tk.Y)
      self.filelist.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=1)
      self.filepanel.pack(fill=Tk.BOTH, expand=1)
      
      # Branch specification pane
      self.branchpanel = Tk.Label(master, text="Branch A: %s       Branch B: %s" % (branchA, branchB))
      self.branchpanel.pack(side=Tk.TOP, fill=Tk.Y)

      # Create subproject navigation widgets
      self.projpanel = Tk.Frame()
      self.projlabel = Tk.Label(self.projpanel, text="Double click to choose a project")
      self.projscroll = Tk.Scrollbar(self.projpanel, width=10)
      self.projlist = Tk.Listbox(self.projpanel, background=bginit, foreground=fginit, selectbackground=bgselected, selectforeground=fgselected, yscrollcommand=self.projscroll.set, selectmode=Tk.SINGLE)
      self.projscroll.config(command=self.projlist.yview)
      self.projlist.bind("<Double-Button-1>", lambda e: self.chooseProject())

      # Place subproject navigation widgets
      self.projscroll.pack(side=Tk.LEFT, fill=Tk.Y)
      self.projlabel.pack(side=Tk.TOP, fill=Tk.X)
      self.projlist.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=1)
      self.projpanel.pack(fill=Tk.BOTH, expand=1)

      # Populate subproject navigation list

      # Outer level repo
      self.projects = [ "" ]
      self.projtype = [ "Outer" ]
      self.projlist.insert(Tk.END, "<Outer Level Project>")

      # Nested subprojects
      activeNestedSubprojects = (grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes())
      inactiveNestedSubprojects = list(set(grapeConfig.grapeConfig().getAllNestedSubprojects()) - set(grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojects()))
      
      self.projects.extend(activeNestedSubprojects)
      for proj in activeNestedSubprojects:
         self.projlist.insert(Tk.END, "%s <Nested Subproject>" % proj)
         self.projtype.append("Active Nested")
      self.projects.extend(inactiveNestedSubprojects)
      for proj in inactiveNestedSubprojects:
         self.projlist.insert(Tk.END, "%s <Inactive Nested Subproject>" % proj)
         self.projtype.append("Inactive Nested")

      # Submodules
      activeSubmodules = (git.getActiveSubmodules())
      inactiveSubmodules = list(set(git.getAllSubmodules()) - set(git.getActiveSubmodules()))
      
      self.projects.extend(activeSubmodules)
      for proj in activeSubmodules:
         self.projlist.insert(Tk.END, "%s <Submodule>" % proj)
         self.projtype.append("Submodule")
      self.projects.extend(inactiveSubmodules)
      for proj in inactiveSubmodules:
         self.projlist.insert(Tk.END, "%s <Inactive Submodule>" % proj)
         self.projtype.append("Inactive Submodule")

      # Subtrees
      # These should also show up in the outer level repo diff, but this
      # should provide the ability to diff just the subproject.
      allSubtrees = [ self.grapeconfig.get('subtree-%s' % proj, 'prefix') for proj in self.grapeconfig.get('subtrees', 'names').strip().split() ]
      self.projects.extend(allSubtrees)
      for proj in allSubtrees:
         self.projlist.insert(Tk.END, "%s <Subtree>" % proj)
         self.projtype.append("Subtree")

      # Resize the project pane based on its contents
      self.projlistwidth = 0
      for proj in self.projlist.get(0, Tk.END):
         if len(proj) > self.projlistwidth:
            self.projlistwidth = len(proj)
      self.projlist.config(width=self.projlistwidth)

      # Place the panes in the main window 
      self.main.add(self.projpanel)
      self.main.add(self.filepanel)
      self.main.pack(fill=Tk.BOTH, expand=1, side=Tk.BOTTOM)

   def initFiles(self, index):
      self.filelist.delete(0,Tk.END)
      dir = self.projects[index]
      type = self.projtype[index]
      if type.startswith("Inactive"):
         pass
      else:
         os.chdir(os.path.join(utility.workspaceDir(), dir))
         self.filenames = []
         diffoutput = git.diff("--name-status %s %s %s" % (self.diffargs, self.branchA, self.branchB), quiet=True).splitlines()
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
               self.filelist.insert(Tk.END, "%s %s" % (file, statusstring))
               self.filenames.append(file)
         else:
            self.filelist.insert(Tk.END, "<No differences>")
            self.filenames.append("")

   def chooseProject(self):
      index = self.projlist.index(Tk.ACTIVE)
      try:
         self.initFiles(index)
         self.projlist.itemconfig(index, bg=bgactive, fg=fgactive)
         self.projlist.itemconfig(self.oldprojindex, bg=bgdone, fg=fgdone)
         self.oldprojindex = index
      except:
         pass
      self.master.update()

   def spawnDiff(self):
      index = self.filelist.index(Tk.ANCHOR)
      try:
         file = self.filenames[index]
         if file != "":
            t = threading.Thread(target=self.runDiff, kwargs={'file':file})
            t.start()
            self.filelist.itemconfig(index, bg=bgdone, fg=fgdone)
      except:
         pass
   def runDiff(self, file):
      difftooloutput = git.gitcmd("difftool -t %s -y %s %s %s \"%s\"" % (self.difftool, self.diffargs, self.branchA, self.branchB, file), "Failed to launch difftool", quiet=False)

