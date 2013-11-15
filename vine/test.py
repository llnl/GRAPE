from __future__ import absolute_import
import os,sys
from vine import option, utility
from .grapeConfig import grapeConfig
if not ".." in sys.path:
    sys.path.append( ".." )
import git

class Test(option.Option):
    def __init__(self):
        self._key = "test"
        self._section = "Other"

    def description(self):
        return "Test Grape."

    def execute(self):

        from test import GrapeTest
        good = GrapeTest.main()
        if not good:
            print "*"*80
            print "*"*80
            print "Hey, a test has failed"
            print "*"*80
            print "*"*80

        return True
