from abc import ABC, abstractmethod


class Option(ABC):

    SECTION_FLOW = 'flow'
    SECTION_NESTED_PROJECTS = 'nestedProjects'
    SECTION_PATCH = 'patch'
    SECTION_POST_CHECKOUT = 'post-checkout'
    SECTION_PROJECT = 'project'
    SECTION_PUBLISH = 'publish'
    SECTION_REPO = 'repo'
    SECTION_SPACK_PROJECTS = 'spackProjects'
    SECTION_REVIEW = 'review'
    SECTION_VERSIONING = 'versioning'
    SECTION_WORKSPACE = 'workspace'
    SECTION_WALKTHROUGH = "walkthrough"

    def __init__(self):
        self._key = "UNSET KEY"
        self._section = "UNSET SECTION"

    @abstractmethod
    def description(self):
        pass

    @abstractmethod
    def execute(self, args):
        pass

    @abstractmethod
    def setDefaultConfig(self, config):
        pass

    @property
    def key(self):
        return self._key

    @property
    def section(self):
        return self._section
