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
      self.difftool = difftool
      self.branchA = branchA
      self.branchB = branchB
      self.diffargs = diffargs
      self.main = Tk.PanedWindow(master, height=height, width=width, sashwidth=4)
      self.filepanel = Tk.Frame()
      self.filelabel = Tk.Label(self.filepanel, text="Double click to launch %s" % self.difftool)
      self.filescroll = Tk.Scrollbar(self.filepanel, width=10)
      self.filelist = Tk.Listbox(self.filepanel, background=bginit, foreground=fginit, selectbackground=bgselected, selectforeground=fgselected, yscrollcommand=self.filescroll.set, selectmode=Tk.SINGLE)
      self.filescroll.config(command=self.filelist.yview)
      self.filelist.bind("<Double-Button-1>", lambda e: self.spawnDiff())

      self.filelabel.pack(side=Tk.TOP, fill=Tk.X)
      self.filescroll.pack(side=Tk.RIGHT, fill=Tk.Y)
      self.filelist.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=1)
      self.filepanel.pack(fill=Tk.BOTH, expand=1)
      
      self.branchpanel = Tk.Label(master, text="Branch A: %s       Branch B: %s" % (branchA, branchB))
      self.branchpanel.pack(side=Tk.TOP, fill=Tk.Y)

      self.projpanel = Tk.Frame()
      self.projlabel = Tk.Label(self.projpanel, text="Double click to choose a project")
      self.projscroll = Tk.Scrollbar(self.projpanel, width=10)
      self.projlist = Tk.Listbox(self.projpanel, background=bginit, foreground=fginit, selectbackground=bgselected, selectforeground=fgselected, yscrollcommand=self.projscroll.set, selectmode=Tk.SINGLE)
      self.projscroll.config(command=self.projlist.yview)
      self.projlist.bind("<Double-Button-1>", lambda e: self.chooseProject())

      self.projscroll.pack(side=Tk.LEFT, fill=Tk.Y)
      self.projlabel.pack(side=Tk.TOP, fill=Tk.X)
      self.projlist.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=1)
      self.projpanel.pack(fill=Tk.BOTH, expand=1)

      self.projects = [ "" ]
      self.projlist.insert(Tk.END, "<Outer Level Project>")

      nestedSubprojects = (grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes())
      
      self.projects.extend(nestedSubprojects)
      for proj in nestedSubprojects:
         self.projlist.insert(Tk.END, "%s <Nested Subproject>" % proj)

      self.projlistwidth = 0
      for proj in self.projlist.get(0, Tk.END):
         if len(proj) > self.projlistwidth:
            self.projlistwidth = len(proj)
      self.projlist.config(width=self.projlistwidth)

      self.main.add(self.projpanel)
      self.main.add(self.filepanel)
      self.main.pack(fill=Tk.BOTH, expand=1, side=Tk.BOTTOM)
      
      self.initFiles("")

   def initFiles(self, dir):
      self.filelist.delete(0,Tk.END)
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
            [status, file] = line.split() 
            statusstring = statusdict[status[0]]
            self.filelist.insert(Tk.END, "%s %s" % (file, statusstring))
            self.filenames.append(file)
      else:
         self.filelist.insert(Tk.END, "<No differences>")
         self.filenames.append("")

   def chooseProject(self):
      index = self.projlist.index(Tk.ACTIVE)
      try:
         self.initFiles(self.projects[index])
         for i in range(0, self.projlist.size()):
            self.projlist.itemconfig(i, bg=bginit, fg=fginit)
         self.projlist.itemconfig(index, bg=bgactive, fg=fgactive)
         Tk.update()
      except:
         pass

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
      difftooloutput = git.gitcmd("difftool -t %s -y %s %s %s %s" % (self.difftool, self.diffargs, self.branchA, self.branchB, file), "Failed to launch difftool", quiet=False)

