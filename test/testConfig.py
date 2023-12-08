import os
from unittest.mock import patch
from test import testGrape


class TestConfig(testGrape.TestGrape):

    @patch('vine.utility.userInput')
    def testConfig(self, mock_userInput):
        mock_userInput.side_effect = ["\n", "\n", "\n", "\n"]
        self.menu.applyMenuChoice("config")
        contents = self.get_output()
        self.assertTrue(contents)
