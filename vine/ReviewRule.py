"""
Class representing a GRAPE review rule.
"""

import re
from typing import List, Dict, Optional, Any


class ApproveInput:
    """
    Represents an approve input configuration for a review rule.
    """

    def __init__(self,
                 prompt: str,
                 source: str = 'prompt',
                 default: Optional[str] = None,
                 label: Optional[str] = None,
                 help: str = '',
                 examples: Optional[Dict[str, str]] = None,
                 substitutions: Optional[Dict[str, str]] = None,
                 tag: bool = True,
                 description: bool = True,
                 required: bool = False,
                 cache: bool = False):
        """
        Initialize an ApproveInput.

        :param prompt: The prompt name/text
        :param source: Source of the input ('prompt', 'username', 'commit', 'tag')
        :param default: Default value for the input
        :param label: Label for the input
        :param help: Help text for the input
        :param examples: Dictionary of examples
        :param substitutions: Dictionary of text substitutions
        :param tag: Whether to use this input in tags
        :param description: Whether to use this input in description
        :param required: Whether this input is required
        :param cache: Whether to cache this input
        """
        self.source = source
        self.prompt = prompt
        self.default = default
        self.label = label if label is not None else prompt
        self.help = help
        self.examples = examples if examples is not None else {}
        self.substitutions = substitutions if substitutions is not None else {}
        self.tag = tag
        self.description = description
        self.required = required
        self.cache = cache

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the ApproveInput to a dictionary.

        :return: Dictionary representation of the ApproveInput
        """
        return {
            'source': self.source,
            'prompt': self.prompt,
            'default': self.default,
            'label': self.label,
            'help': self.help,
            'examples': self.examples,
            'substitutions': self.substitutions,
            'tag': self.tag,
            'description': self.description,
            'required': self.required,
            'cache': self.cache
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ApproveInput':
        """
        Create an ApproveInput from a dictionary.

        :param data: Dictionary containing ApproveInput data
        :return: ApproveInput instance
        """
        return cls(
            source=data.get('source', 'prompt'),
            prompt=data.get('prompt', ''),
            default=data.get('default'),
            label=data.get('label'),
            help=data.get('help', ''),
            examples=data.get('examples', {}),
            substitutions=data.get('substitutions', {}),
            tag=data.get('tag', True),
            description=data.get('description', True),
            required=data.get('required', False),
            cache=data.get('cache', False)
        )


class ReviewRule:
    """
    Represents a GRAPE review rule with all its configuration options.
    """

    def __init__(self,
                 name: str,
                 active: bool = True,
                 label: Optional[str] = None,
                 minNumReviewers: int = 1,
                 authorEligible: bool = False,
                 eligibleReviewers: Optional[List[str]] = None,
                 repositories: Optional[List[str]] = None,
                 approveActions: Optional[List[str]] = None,
                 approveInputs: Optional[List[ApproveInput]] = None,
                 dryRun: bool = False):
        """
        Initialize a ReviewRule.

        :param name: Name of the review rule
        :param active: Whether the rule is active
        :param label: Label for the rule (defaults to "GRAPE: {name} review")
        :param minNumReviewers: Minimum number of reviewers required
        :param authorEligible: Whether the author can review/approve
        :param eligibleReviewers: List of eligible reviewer patterns
        :param repositories: List of repository patterns this rule applies to
        :param approveActions: List of actions to perform on approval
        :param approveInputs: List of ApproveInput configurations
        :param dryRun: Whether to run in dry-run mode
        """
        self._name = name
        self._active = active
        self._label = label if label is not None else f"GRAPE: {name} review"
        self._minNumReviewers = minNumReviewers
        self._authorEligible = authorEligible
        self._eligibleReviewers = eligibleReviewers if eligibleReviewers is not None else [".+"]
        self._repositories = repositories if repositories is not None else [".+"]
        self._approveActions = approveActions if approveActions is not None else ['approve']
        self._approveInputs = approveInputs if approveInputs is not None else []
        self._dryRun = dryRun

    @property
    def name(self) -> str:
        """Get the name of the review rule."""
        return self._name

    @property
    def active(self) -> bool:
        """Get whether the rule is active."""
        return self._active

    @property
    def label(self) -> str:
        """Get the label for the rule."""
        return self._label

    @property
    def minNumReviewers(self) -> int:
        """Get the minimum number of reviewers required."""
        return self._minNumReviewers

    @property
    def authorEligible(self) -> bool:
        """Get whether the author can review/approve."""
        return self._authorEligible

    @property
    def eligibleReviewers(self) -> List[str]:
        """Get the list of eligible reviewer patterns."""
        return self._eligibleReviewers

    @property
    def repositories(self) -> List[str]:
        """Get the list of repository patterns this rule applies to."""
        return self._repositories

    @property
    def approveActions(self) -> List[str]:
        """Get the list of actions to perform on approval."""
        return self._approveActions

    @property
    def approveInputs(self) -> List[ApproveInput]:
        """Get the list of ApproveInput configurations."""
        return self._approveInputs

    @property
    def dryRun(self) -> bool:
        """Get whether to run in dry-run mode."""
        return self._dryRun

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the ReviewRule to a dictionary.

        :return: Dictionary representation of the ReviewRule
        """
        return {
            'name': self.name,
            'active': self.active,
            'label': self.label,
            'minNumReviewers': self.minNumReviewers,
            'authorEligible': self.authorEligible,
            'eligibleReviewers': self.eligibleReviewers,
            'repositories': self.repositories,
            'approveActions': self.approveActions,
            'approveInputs': [
                input_obj.to_dict() if isinstance(input_obj, ApproveInput) else input_obj
                for input_obj in self.approveInputs
            ],
            'dryRun': self.dryRun
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ReviewRule':
        """
        Create a ReviewRule from a dictionary.

        :param data: Dictionary containing ReviewRule data
        :return: ReviewRule instance
        """
        # Convert approveInputs dicts to ApproveInput objects
        approve_inputs = []
        for input_data in data.get('approveInputs', []):
            if isinstance(input_data, dict):
                approve_inputs.append(ApproveInput.from_dict(input_data))
            elif isinstance(input_data, ApproveInput):
                approve_inputs.append(input_data)

        return cls(
            name=data['name'],
            active=data.get('active', True),
            label=data.get('label'),
            minNumReviewers=data.get('minNumReviewers', 1),
            authorEligible=data.get('authorEligible', False),
            eligibleReviewers=data.get('eligibleReviewers'),
            repositories=data.get('repositories'),
            approveActions=data.get('approveActions'),
            approveInputs=approve_inputs,
            dryRun=data.get('dryRun', False)
        )

    def matches_repository(self, name: str) -> bool:
        """
        Determine whether this review rule applies to a repository.

        Checks the given respository name against each regex pattern in the
        repositories list using re.fullmatch.

        :param name: Repository name to test
        :return: True if any repository pattern fully matches name, otherwise False
        """
        for repo_pattern in self.repositories:
            if re.fullmatch(repo_pattern, name):
                return True

        return False

    def matches_reviewer(self, name: str) -> bool:
        """
        Determine whether a reviewer is eligible for this review rule.

        Checks the given reviewer against each regex pattern in the
        eligibleReviewers list using re.fullmatch.

        :param name: Reviewer name/username to test
        :return: True if any eligible reviewer pattern fully matches name, otherwise False
        """
        for reviewer_pattern in self.eligibleReviewers:
            if re.fullmatch(reviewer_pattern, name):
                return True

        return False

    def __repr__(self) -> str:
        """
        Return a string representation of the ReviewRule.

        :return: String representation
        """
        return (f"ReviewRule(name='{self.name}', active={self.active}, "
                f"label='{self.label}', minNumReviewers={self.minNumReviewers})")
