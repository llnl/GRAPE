"""
Class representing a GRAPE review rule.
"""

import ast
import logging
import re
from typing import List, Dict, Optional, Any


class ApproveInput:
    """
    Represents an approve input configuration for a review rule.
    """

    def __init__(self,
                 source: str = 'prompt',
                 prompt: Optional[str] = None,
                 default: Optional[str] = None,
                 label: Optional[str] = None,
                 help: str = '',
                 examples: Optional[Dict[str, str]] = None,
                 substitutions: Optional[Dict[str, str]] = None,
                 tag: bool = True,
                 description: bool = True,
                 required: bool = False,
                 cache: bool = False,
                 value: Optional[str] = None):
        """
        Initialize an ApproveInput.

        :param source: Source of the input ('prompt', 'username', 'commit', 'tag')
        :param prompt: The prompt name/text
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
        self.value = value


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

    @classmethod
    def from_config(cls, config, reviewRuleName: str, reservedReviewRuleLabels: Optional[List[str]] = None) -> 'ReviewRule':
        """
        Create a ReviewRule from a config file.

        :param config: ConfigParser object containing the review rule configuration
        :param reviewRuleName: Name of the review rule to parse
        :param reservedReviewRuleLabels: List of reserved labels that cannot be used (optional)
        :return: ReviewRule instance created from the config
        """
        if reservedReviewRuleLabels is None:
            reservedReviewRuleLabels = []

        sectionName = f"review-{reviewRuleName}"

        if not config.has_section(sectionName):
            logging.error(f'GRAPE: ERROR: Global config section "{sectionName}" is missing.')
            exit(1)

        # Default to active
        active = True
        if config.has_option(sectionName, "active"):
            active = config.getboolean(sectionName, "active")

        # Provide a reasonable default for the rule label
        label = f"GRAPE: {reviewRuleName} review"
        if config.has_option(sectionName, "label"):
            label = config.get(sectionName, "label")

        if label in reservedReviewRuleLabels:
            logging.error(f'GRAPE: ERROR: The review rule label "{label}" is reserved by GRAPE.')
            exit(1)

        # Default to one reviewer
        minNumReviewers = 1
        if config.has_option(sectionName, "minnumreviewers"):
            minNumReviewers = config.getint(sectionName, "minnumreviewers")

        # Default to not allowing the author to review/approve
        authorEligible = False
        if config.has_option(sectionName, "authoreligible"):
            authorEligible = config.getboolean(sectionName, "authoreligible")

        # Default to all reviewers
        eligibleReviewers = [".+"]
        if config.has_option(sectionName, "eligiblereviewers"):
            eligibleReviewers = config.get(sectionName, "eligiblereviewers").split()

        # Default to all repositories
        repositories = [".+"]
        if config.has_option(sectionName, "repositories"):
            repositories = config.get(sectionName, "repositories").split()

        # Get approve actions
        approveActions = ['approve']
        if config.has_option(sectionName, "approveactions"):
            approveActions = config.get(sectionName, "approveactions").split()

        # Get approve inputs
        approveInputNames = []
        if config.has_option(sectionName, "approveinputs"):
            approveInputNames = config.get(sectionName, "approveinputs").split()

            if len(approveInputNames) != len(set(approveInputNames)):
                logging.warning(f'GRAPE: WARNING: Duplicate approve input variables.')

        approveInputs = []

        for approveInputName in approveInputNames:
            approveInputSource = 'prompt'
            approveInputPrompt = approveInputName
            approveInputDefault = None
            approveInputLabel = approveInputName
            approveInputHelp = ''
            approveInputExamples = {}
            approveInputSubstitutions = {}
            approveInputTag = True
            approveInputDescription = True
            approveInputRequired = False
            approveInputCache = False

            approveInputSectionName = f"{sectionName}-approve-inputs-{approveInputName}"

            if config.has_section(approveInputSectionName):
                if config.has_option(approveInputSectionName, "source"):
                    approveInputSource = config.get(approveInputSectionName, "source")
                    validSources = ["prompt", "username", "commit", "tag"]

                    if approveInputSource not in validSources:
                        logging.error(f'GRAPE: ERROR: Global config section "{approveInputSectionName}" has invalid value "{approveInputSource}" for "source". Supported values include {", ".join(validSources)}".')
                        exit(1)

                if config.has_option(approveInputSectionName, "prompt"):
                    if approveInputSource != "prompt":
                        logging.error(f'GRAPE: ERROR: Global config section "{approveInputSectionName}" must not specify a prompt if the source is not a prompt.')
                        exit(1)

                    approveInputPrompt = config.get(approveInputSectionName, "prompt")

                if config.has_option(approveInputSectionName, "default"):
                    if approveInputSource != "prompt":
                        logging.error(f'GRAPE: ERROR: Global config section "{approveInputSectionName}" must not specify a default value if the source is not a prompt.')
                        exit(1)

                    approveInputDefault = config.get(approveInputSectionName, "default")

                if config.has_option(approveInputSectionName, "label"):
                    approveInputLabel = config.get(approveInputSectionName, "label")

                if config.has_option(approveInputSectionName, "help"):
                    approveInputHelp = config.get(approveInputSectionName, "help")

                if config.has_option(approveInputSectionName, "examples"):
                    examples = config.get(approveInputSectionName, "examples")

                    try:
                        examples = ast.literal_eval(examples)
                    except:
                        logging.error(f'GRAPE: ERROR: Global config section "{approveInputSectionName}" must specify "examples" as a python dictionary (e.g. {{key1: description1, key2: description2, ...}}')
                        exit(1)

                    if not isinstance(examples, dict):
                        logging.error(f'GRAPE: ERROR: Global config section "{approveInputSectionName}" must specify "examples" as a python dictionary (e.g. {{key1: description1, key2: description2, ...}}')
                        exit(1)

                    approveInputExamples = examples

                if config.has_option(approveInputSectionName, "substitutions"):
                    substitutions = config.get(approveInputSectionName, "substitutions")

                    try:
                        substitutions = ast.literal_eval(substitutions)
                    except:
                        logging.error(f'GRAPE: ERROR: Global config section "{approveInputSectionName}" must specify "substitutions" as a python dictionary (e.g. {{"text1": "substitution1", "text2": "substitution2", ...}}')
                        exit(1)

                    if not isinstance(substitutions, dict):
                        logging.error(f'GRAPE: ERROR: Global config section "{approveInputSectionName}" must specify "substitutions" as a python dictionary (e.g. {{"text1": "substitution1", "text2": "substitution2", ...}}')
                        exit(1)

                    temp = {}
                    values = set()

                    for key, val in substitutions.items():
                        key_str = str(key)
                        val_str = str(val)
                        temp[key_str] = val_str

                        for value in values:
                            if key_str in value:
                                logging.warning(f'GRAPE: WARNING: Global config section "{approveInputSectionName}" has overlapping substitutions. This may result in unexpected substitutions.')

                        values.add(val_str)

                    substitutions = temp
                    approveInputSubstitutions = substitutions

                if config.has_option(approveInputSectionName, "tag"):
                    approveInputTag = config.getboolean(approveInputSectionName, "tag")

                    if approveInputTag and 'tag' not in approveActions:
                        logging.error(f'GRAPE: ERROR: Global config section "{approveInputSectionName}" does not support "True" for the "tag" option (review rule "{reviewRuleName}" does not create a tag on approval).')
                        exit(1)

                if config.has_option(approveInputSectionName, "description"):
                    approveInputDescription = config.getboolean(approveInputSectionName, "description")

                    if approveInputDescription and 'description' not in approveActions:
                        logging.error(f'GRAPE: ERROR: Global config section "{approveInputSectionName}" does not support "True" for the "description" option (review rule "{reviewRuleName}" does not update the description on approval).')
                        exit(1)

                if config.has_option(approveInputSectionName, "required"):
                    approveInputRequired = config.getboolean(approveInputSectionName, "required")

                if config.has_option(approveInputSectionName, "cache"):
                    approveInputCache = config.getboolean(approveInputSectionName, "cache")

                    cacheableSources = ["prompt", "username"]

                    if approveInputCache and approveInputSource not in cacheableSources:
                        logging.error(f'GRAPE: ERROR: Global config section "{approveInputSectionName}" has source "{approveInputSource}" which cannot be cached. Sources that can be cached include {", ".join(cacheableSources)}.')
                        exit(1)

                # Check if the approve input is actually used
                if not approveInputDescription and not approveInputTag:
                    logging.warning(f'GRAPE: WARNING: Approve input variable "{approveInputName}" is unused.')
                    continue

            approveInputs.append(
                ApproveInput(
                    source=approveInputSource,
                    prompt=approveInputPrompt,
                    default=approveInputDefault,
                    label=approveInputLabel,
                    help=approveInputHelp,
                    examples=approveInputExamples,
                    substitutions=approveInputSubstitutions,
                    tag=approveInputTag,
                    description=approveInputDescription,
                    required=approveInputRequired,
                    cache=approveInputCache
                )
            )

        # Controls whether publish checks are just reported or actually prevent a publish
        dryRun = False
        if config.has_option(sectionName, "dryrun"):
            dryRun = config.getboolean(sectionName, "dryrun")

        return cls(
            name=reviewRuleName,
            active=active,
            label=label,
            minNumReviewers=minNumReviewers,
            authorEligible=authorEligible,
            eligibleReviewers=eligibleReviewers,
            repositories=repositories,
            approveActions=approveActions,
            approveInputs=approveInputs,
            dryRun=dryRun
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

