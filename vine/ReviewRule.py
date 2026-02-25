"""
Class representing a GRAPE review rule.
"""

import ast
import logging
import re
from typing import List, Dict, Optional, Any


class ApproveInputDefinition:
    """
    Defines an input to be collected on approval applied to a review rule.
    Input is collected for each modified repository that is approved by the
    user and to which the review rule applies.
    """

    def __init__(self,
                 source: str = 'prompt',
                 prompt: Optional[str] = None,
                 default: Optional[str] = None,
                 label: Optional[str] = None,
                 help: str = '',
                 examples: Optional[Dict[str, str]] = None,
                 substitutions: Optional[Dict[str, str]] = None,
                 include_in_tag: bool = True,
                 include_in_description: bool = True,
                 required: bool = False,
                 cache: bool = False,
                 value: Optional[str] = None):
        """
        Initialize an ApproveInputDefinition.

        Parameters
        ----------
        source : str
            Source of the input ('prompt', 'username', 'commit', 'tag', 'date'). Default is 'prompt'.
        prompt : str, optional
            The prompt name/text.
        default : str, optional
            Default value for the input.
        label : str, optional
            Label for the input. Defaults to prompt if not specified.
        help : str
            Help text for the input. Default is empty string.
        examples : dict, optional
            Dictionary of examples.
        substitutions : dict, optional
            Dictionary of text substitutions.
        include_in_tag : bool
            Whether to use this input in tags. Default is True.
        include_in_description : bool
            Whether to use this input in description. Default is True.
        required : bool
            Whether this input is required. Default is False.
        cache : bool
            Whether to cache this input. Default is False.
        value : str, optional
            The value for this input.
        """
        self.source = source
        self.prompt = prompt
        self.default = default
        self.label = label if label is not None else prompt
        self.help = help
        self.examples = examples if examples is not None else {}
        self.substitutions = substitutions if substitutions is not None else {}
        self.include_in_tag = include_in_tag
        self.include_in_description = include_in_description
        self.required = required
        self.cache = cache
        self.value = value

    @classmethod
    def from_config(cls, config, review_rule_id: str, approve_input_id: str, approve_actions: List[str]) -> Optional['ApproveInputDefinition']:
        """
        Create an ApproveInputDefinition from a config file.

        Parameters
        ----------
        config : ConfigParser
            ConfigParser object containing the approve input configuration.
        review_rule_id : str
            ID of the review rule.
        approve_input_id : str
            ID of the approve input.
        approve_actions : list of str
            List of approve actions for the parent rule (used for validation).

        Returns
        -------
        ApproveInputDefinition or None
            ApproveInputDefinition instance created from the config, or None if the config section does not exist.
        """
        source = 'prompt'
        prompt = approve_input_id
        default_value = None
        label = approve_input_id
        help_text = ''
        examples = {}
        substitutions = {}
        include_in_tag = True
        include_in_description = True
        required = False
        cache = False

        section_name = f"review-{review_rule_id}-approve-inputs-{approve_input_id}"

        if config.has_section(section_name):
            if config.has_option(section_name, "source"):
                source = config.get(section_name, "source")
                validSources = ["prompt", "username", "commit", "tag", "date"]

                if source not in validSources:
                    logging.error(f'GRAPE: ERROR: Global config section "{section_name}" has invalid value "{source}" for "source". Supported values include {", ".join(validSources)}".')
                    exit(1)

            if config.has_option(section_name, "prompt"):
                if source != "prompt":
                    logging.error(f'GRAPE: ERROR: Global config section "{section_name}" must not specify a prompt if the source is not a prompt.')
                    exit(1)

                prompt = config.get(section_name, "prompt")

            if config.has_option(section_name, "default"):
                if source != "prompt":
                    logging.error(f'GRAPE: ERROR: Global config section "{section_name}" must not specify a default value if the source is not a prompt.')
                    exit(1)

                default_value = config.get(section_name, "default")

            if config.has_option(section_name, "label"):
                label = config.get(section_name, "label")

            if config.has_option(section_name, "help"):
                help_text = config.get(section_name, "help")

            if config.has_option(section_name, "examples"):
                examples = config.get(section_name, "examples")

                try:
                    examples = ast.literal_eval(examples)
                except:
                    logging.error(f'GRAPE: ERROR: Global config section "{section_name}" must specify "examples" as a python dictionary (e.g. {{key1: description1, key2: description2, ...}}')
                    exit(1)

                if not isinstance(examples, dict):
                    logging.error(f'GRAPE: ERROR: Global config section "{section_name}" must specify "examples" as a python dictionary (e.g. {{key1: description1, key2: description2, ...}}')
                    exit(1)

                examples = examples

            if config.has_option(section_name, "substitutions"):
                substitutions = config.get(section_name, "substitutions")

                try:
                    substitutions = ast.literal_eval(substitutions)
                except:
                    logging.error(f'GRAPE: ERROR: Global config section "{section_name}" must specify "substitutions" as a python dictionary (e.g. {{"text1": "substitution1", "text2": "substitution2", ...}}')
                    exit(1)

                if not isinstance(substitutions, dict):
                    logging.error(f'GRAPE: ERROR: Global config section "{section_name}" must specify "substitutions" as a python dictionary (e.g. {{"text1": "substitution1", "text2": "substitution2", ...}}')
                    exit(1)

                temp = {}
                values = set()

                for key, val in substitutions.items():
                    key_str = str(key)
                    val_str = str(val)
                    temp[key_str] = val_str

                    for value in values:
                        if key_str in value:
                            logging.warning(f'GRAPE: WARNING: Global config section "{section_name}" has overlapping substitutions. This may result in unexpected substitutions.')

                    values.add(val_str)

                substitutions = temp
                substitutions = substitutions

            if config.has_option(section_name, "tag"):
                include_in_tag = config.getboolean(section_name, "tag")

                if include_in_tag and 'tag' not in approve_actions:
                    logging.error(f'GRAPE: ERROR: Global config section "{section_name}" does not support "True" for the "tag" option (review rule "{review_rule_id}" does not create a tag on approval).')
                    exit(1)

            if config.has_option(section_name, "description"):
                include_in_description = config.getboolean(section_name, "description")

                if include_in_description and 'description' not in approve_actions:
                    logging.error(f'GRAPE: ERROR: Global config section "{section_name}" does not support "True" for the "description" option (review rule "{review_rule_id}" does not update the description on approval).')
                    exit(1)

            if config.has_option(section_name, "required"):
                required = config.getboolean(section_name, "required")

            if config.has_option(section_name, "cache"):
                cache = config.getboolean(section_name, "cache")

                cacheableSources = ["prompt", "username"]

                if cache and source not in cacheableSources:
                    logging.error(f'GRAPE: ERROR: Global config section "{section_name}" has source "{source}" which cannot be cached. Sources that can be cached include {", ".join(cacheableSources)}.')
                    exit(1)

            # Check if the approve input is actually used
            if not include_in_description and not include_in_tag:
                logging.warning(f'GRAPE: WARNING: Approve input variable "{approve_input_id}" is unused.')
                return None

        return cls(
            source=source,
            prompt=prompt,
            default=default_value,
            label=label,
            help=help_text,
            examples=examples,
            substitutions=substitutions,
            include_in_tag=include_in_tag,
            include_in_description=include_in_description,
            required=required,
            cache=cache
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
                 approveInputs: Optional[List[ApproveInputDefinition]] = None,
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
        :param approveInputs: List of ApproveInputDefinition configurations
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
    def approveInputs(self) -> List[ApproveInputDefinition]:
        """Get the list of ApproveInputDefinition configurations."""
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
        :param reservedReviewRuleLabels: List of reserved labels that cannot be used (optional).
                                        Should typically be obtained from ReviewRuleManager.get_reserved_labels().
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
            approveInput = ApproveInputDefinition.from_config(
                config,
                reviewRuleName,
                approveInputName,
                approveActions
            )
            if approveInput is not None:
                approveInputs.append(approveInput)

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


class ReviewRuleManager:
    """
    Manages the collection of review rules, rule mappings, and default rule selection.
    """

    def __init__(self,
                 reviewRules: Dict[str, ReviewRule],
                 reviewRuleMap: Dict[str, str],
                 defaultReviewRuleName: str):
        """
        Initialize a ReviewRuleManager.

        :param reviewRules: Dictionary mapping review rule names to ReviewRule objects
        :param reviewRuleMap: Dictionary mapping old rule names to new rule names
        :param defaultReviewRuleName: Name of the default review rule
        """
        self._reviewRules = reviewRules
        self._reviewRuleMap = reviewRuleMap
        self._defaultReviewRuleName = defaultReviewRuleName
        # Pre-compute list of active rule names
        self._activeRuleNames = [name for name, rule in reviewRules.items() if rule.active]

    @property
    def reviewRules(self) -> Dict[str, ReviewRule]:
        """Get the dictionary of review rules."""
        return self._reviewRules

    @property
    def reviewRuleMap(self) -> Dict[str, str]:
        """Get the dictionary mapping old rule names to new rule names."""
        return self._reviewRuleMap

    @property
    def defaultReviewRuleName(self) -> str:
        """Get the name of the default review rule."""
        return self._defaultReviewRuleName

    @property
    def activeRuleNames(self) -> List[str]:
        """Get the list of active review rule names."""
        return self._activeRuleNames

    def get_default_rule(self) -> Optional[ReviewRule]:
        """
        Get the default review rule.

        :return: ReviewRule instance for the default rule, or None if not found
        """
        return self._reviewRules.get(self._defaultReviewRuleName)

    def get_rule(self, name: str) -> Optional[ReviewRule]:
        """
        Get a review rule by name.

        If the rule name is in the rule map, it will be resolved to the mapped name.

        :param name: Name of the review rule to retrieve
        :return: ReviewRule instance if found, None otherwise
        """
        # Check if the name is mapped to a different name
        if name in self._reviewRuleMap:
            name = self._reviewRuleMap[name]

        return self._reviewRules.get(name)

    @staticmethod
    def get_default_grape_rule(active: bool) -> ReviewRule:
        """
        Create the default GRAPE review rule.

        The GRAPE review rule is used when no user-specified rules are found in the
        global config. It will be active only if the user has not specified any rules.

        :param active: Whether or not the GRAPE review rule is active
        :return: ReviewRule object representing the default GRAPE rule
        """
        # Import here to avoid circular dependency
        from vine import Gitlab

        return ReviewRule(
            name='grape',
            active=active,
            label=Gitlab.GRAPE_GITLAB_APPROVAL_RULE_NAME,
            minNumReviewers=1,
            authorEligible=False,
            eligibleReviewers=['.+'],
            repositories=['.+'],
            approveActions=['approve'],
            approveInputs=[],
            dryRun=False
        )

    @staticmethod
    def get_reserved_labels() -> List[str]:
        """
        Get the list of reserved review rule labels.

        These labels are reserved by GRAPE and cannot be used for custom review rules.

        :return: List of reserved label strings
        """
        # Import here to avoid circular dependency
        from vine import Gitlab

        return [Gitlab.GRAPE_GITLAB_APPROVAL_RULE_NAME]

    @classmethod
    def from_config(cls, config=None) -> 'ReviewRuleManager':
        """
        Create a ReviewRuleManager from a config file.

        :param config: ConfigParser object containing the review configuration (optional)
        :return: ReviewRuleManager instance created from the config
        """
        if config is None:
            from vine import config_parser_global
            config = config_parser_global.grapeConfig()

        reviewRules = {}

        # Names reserved by grape
        reservedReviewRuleNames = ['grape']
        reservedReviewRuleLabels = cls.get_reserved_labels()

        # Count the number of active review rules
        numActiveRules = 0

        # Extract the rule names from the [review] section
        reviewSectionName = "review"

        if config.has_section(reviewSectionName):
            if config.has_option(reviewSectionName, "rules"):
                reviewRuleNames = config.get(reviewSectionName, "rules").split()

                for reviewRuleName in reviewRuleNames:
                    if reviewRuleName in reservedReviewRuleNames:
                        logging.error(f'GRAPE: ERROR: The review rule name "{reviewRuleName}" is reserved by GRAPE.')
                        exit(1)

                    # Use ReviewRule.from_config to parse the rule
                    reviewRule = ReviewRule.from_config(config, reviewRuleName, reservedReviewRuleLabels)

                    if reviewRule.active:
                        numActiveRules += 1

                    # Add the rule
                    reviewRules[reviewRuleName] = reviewRule

        # Add the GRAPE review rule. It will be active only if the user has
        # not specified any rules.
        if not reviewRules:
            grapeReviewRuleActive = True
            numActiveRules += 1
        else:
            grapeReviewRuleActive = False

        # Create and add the default GRAPE review rule
        reviewRules['grape'] = cls.get_default_grape_rule(grapeReviewRuleActive)

        if numActiveRules == 0:
            logging.error(f'GRAPE: ERROR: At least one review rule must be active.')
            exit(1)

        # Parse the review rule map
        reviewRuleMap = {}

        if config.has_section(reviewSectionName):
            if config.has_option(reviewSectionName, 'rulemap'):
                mappings = config.get(reviewSectionName, 'rulemap')

                for mapping in mappings.split():
                    tokens = mapping.split(':')

                    if len(tokens) != 2:
                        logging.error(f'GRAPE: ERROR: The rule map should consist of whitespace separated mappings, where each mapping is of the form "oldrule:newrule".')
                        exit(1)

                    oldRule = tokens[0]

                    if oldRule not in reviewRules or reviewRules[oldRule].active:
                        logging.error(f'GRAPE: ERROR: "{oldRule}" in "{mapping}" does not specify an inactive review rule.')
                        exit(1)

                    newRule = tokens[1]

                    if newRule not in reviewRules or not reviewRules[newRule].active:
                        logging.error(f'GRAPE: ERROR: "{newRule}" in "{mapping}" does not specify an active review rule.')
                        exit(1)

                    reviewRuleMap[oldRule] = newRule

        # Parse the default review rule name
        defaultReviewRuleName = ''

        if config.has_section(reviewSectionName):
            if config.has_option(reviewSectionName, "defaultrule"):
                defaultReviewRuleName = config.get(reviewSectionName, "defaultrule")

                # Check that the default matches one of the active review rule names
                if defaultReviewRuleName not in reviewRules or not reviewRules[defaultReviewRuleName].active:
                    logging.error(f'GRAPE: ERROR: The default review rule name "{defaultReviewRuleName}" does not specify an active review rule.')
                    exit(1)

        # If there is only one active review rule, use that as the default
        if not defaultReviewRuleName:
            numActiveReviewRules = 0

            for reviewRuleName in reviewRules:
                if reviewRules[reviewRuleName].active:
                    numActiveReviewRules += 1

            if numActiveReviewRules == 1:
                for reviewRuleName in reviewRules:
                    if reviewRules[reviewRuleName].active:
                        defaultReviewRuleName = reviewRuleName
                        break
            else:
                logging.error(f'GRAPE: ERROR: "defaultrule" in section "{reviewSectionName}" in the global config must be specified.')
                exit(1)

        return cls(reviewRules, reviewRuleMap, defaultReviewRuleName)

