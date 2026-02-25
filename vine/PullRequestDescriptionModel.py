from dataclasses import dataclass, field
from typing import Dict, List, Set
from vine import markdown
from vine import version

import re

@dataclass
class PullRequestDescriptionModel:
    """
    Data representing a pull request description.

    Fields:
      - userLines: free-form lines from the user
      - relatedPullRequests: URLs to other pull requests
      - reviewRules: structured review information
    """
    userLines: List[str] = field(default_factory=list)
    relatedReviews: Set[str] = field(default_factory=set)
    reviewRules: Dict = field(default_factory=dict)

    @classmethod
    def from_text(cls, description, reviewRuleManager):
        if not description:
            return cls(
                userLines=[],
                relatedReviews=set(),
                reviewRules={}
            )

        # Parse into markdown sections
        descriptionDoc = markdown.Document.from_text(description.strip())

        # Section titles
        grapeTitle = 'GRAPE'
        relatedReviewsTitle = 'Related Reviews'
        reviewRulesTitle = 'Review Rules'
        grapeGeneratedTitles = [grapeTitle, relatedReviewsTitle, reviewRulesTitle]

        # Gather all user description lines
        userDescriptionLines = []
        topLevelSection = descriptionDoc.find_section('')
        userDescriptionLines.extend(topLevelSection.lines)

        for child in topLevelSection.children:
            if child.title in grapeGeneratedTitles:
                continue

            for section in child.iter_depth_first():
                userDescriptionLines.append(f'{"#" * section.level} {section.title}')
                userDescriptionLines.extend(section.lines)

        # Gather related reviews
        relatedReviews = set()
        relatedReviewsSection = descriptionDoc.find_section(f'{grapeTitle}/{relatedReviewsTitle}')

        if not relatedReviewsSection:
            relatedReviewsSection = descriptionDoc.find_section(relatedReviewsTitle)

        if relatedReviewsSection:
            for line in relatedReviewsSection.lines:
                line = line.strip()

                if line and line != 'None':
                    relatedReviews.add(line)

        # Gather review rules
        ruleReviewersPattern = re.compile(
            r'^\s*Reviewer\(s\):\s*(?P<reviewers>.+?)\s*$'
        )

        ruleKeyValuePattern = re.compile(
            r'^\s*\*\s*(?P<key>[^:]+?)\s*:\s*(?P<value>.*?)\s*$'
        )

        rules = {}
        rulesSection = descriptionDoc.find_section(f'{grapeTitle}/{reviewRulesTitle}')

        if not rulesSection:
            rulesSection = descriptionDoc.find_section(reviewRulesTitle)

        if rulesSection:
            for ruleSection in rulesSection.children:
                ruleLabel = ruleSection.title
                ruleReviewers = set()

                for line in ruleSection.lines:
                    match = ruleReviewersPattern.match(line)

                    if match:
                        for reviewer in match.group('reviewers').split(','):
                            ruleReviewers.add(reviewer)

                ruleReviewers = ruleReviewers
                ruleApprovals = {}

                for approvalSection in ruleSection.children:
                    repoName = approvalSection.title
                    approvalData = {}

                    for line in approvalSection.lines:
                        match = ruleKeyValuePattern.match(line)

                        if match:
                            approvalData[match.group('key')] = match.group('value')

                    ruleApprovals[repoName] = approvalData

                rules[ruleLabel] = {
                    'reviewers': ruleReviewers,
                    'approvals': ruleApprovals,
                }

        # Review rule reviewers used to be saved in the GRAPE section
        grapeSection = descriptionDoc.find_section(grapeTitle)

        if grapeSection:
            savedReviewersPattern = re.compile(
                r'^\s*--reviewers=(?P<reviewers>.+?)\s*$'
            )

            for line in grapeSection.lines:
                match = savedReviewersPattern.match(line)

                if match:
                    savedReviewers = match.group('reviewers')
                    reviewerGroups = savedReviewers.split()

                    for reviewerGroup in reviewerGroups:
                        tokens = reviewerGroup.split(':')

                        if len(tokens) == 1:
                            reviewRule = reviewRuleManager.get_default_rule()

                            if not reviewRule:
                                logging.warning(f'GRAPE: Warning: No default review rule. Removing reviewer group "{reviewerGroup}"...')
                                continue

                            reviewers = tokens[0]
                        elif len(tokens) == 2:
                            ruleName = tokens[0]
                            reviewRule = reviewRuleManager.get_rule(ruleName)

                            if not reviewRule:
                                logging.warning(f'GRAPE: Warning: Unknown review rule "{ruleName}" in pull request description. Removing reviewer group "{reviewerGroup}"...')
                                continue

                            reviewers = tokens[1]

                        ruleLabel = reviewRule.label

                        # Add review rule data if needed
                        if ruleLabel not in rules:
                            rules[ruleLabel] = {'reviewers': set(), 'approvals': {}}

                        rule = rules[ruleLabel]
                        allReviewers = rule['reviewers']

                        # Check and add reviewers
                        reviewers = set(reviewers.split(','))

                        for reviewer in reviewers:
                            if reviewRule.matches_reviewer(reviewer):
                                allReviewers.add(reviewer)
                            else:
                                logging.warning(f'GRAPE: WARNING: User "{reviewer}" is not allowed as a reviewer for the "{reviewRule.name}" rule. Removing...')

        return cls(
            userLines=userDescriptionLines,
            relatedReviews=relatedReviews,
            reviewRules=rules
        )

    def to_text(self):
        # Begin with user description
        description = '\n'.join(self.userLines)
        description.strip()

        # Add GRAPE section
        description += '\n\n# GRAPE'
        description += f'\n\nGenerated by GRAPE {version.grapeVersion()}.'

        # Add Related Reviews section
        description += '\n\n## Related Reviews'

        if len(self.relatedReviews) > 1:
            description += '\n\n' + '\n\n'.join(sorted(self.relatedReviews))
        else:
            description += '\n\nNone'

        # Add Review Rules section
        if self.reviewRules:
            description += '\n\n## Review Rules'

            for ruleName in self.reviewRules:
                rule = self.reviewRules[ruleName]
                description += f'\n\n### {ruleName}'

                reviewers = ','.join(sorted(rule['reviewers']))

                if reviewers:
                    description += f'\n\nReviewer(s): {reviewers}'

                approvals = rule['approvals']

                for approval in approvals:
                    description += f'\n\n#### {approval}'

                    for key in approvals[approval]:
                        description += f'\n\n* {key}: {approvals[approval][key]}'

        return description

    def set_grape_version(self, version):
        self.grapeVersion = version

    def clear_related_pull_requests(self):
        self.relatedReviews.clear()

    def add_related_pull_request(self, link):
        self.relatedReviews.add(link)
