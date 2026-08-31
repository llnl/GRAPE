from dataclasses import dataclass, field
from typing import Dict, List, Set
import json
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
    stackMetadata: Dict = field(default_factory=dict)

    @classmethod
    def from_text(cls, description, reviewRuleManager):
        if not description:
            return cls(
                userLines=[],
                relatedReviews=set(),
                reviewRules={},
                stackMetadata={}
            )

        # Parse into markdown sections
        descriptionDoc = markdown.Document.from_text(description.strip())

        # Section titles
        grapeTitle = 'GRAPE'
        relatedReviewsTitle = 'Related Reviews'
        reviewRulesTitle = 'Review Rules'
        stackTitle = 'Stack'
        grapeGeneratedTitles = [
            grapeTitle, relatedReviewsTitle, reviewRulesTitle, stackTitle]

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

        stackMetadata = {}
        stackSection = descriptionDoc.find_section(f'{grapeTitle}/{stackTitle}')
        if not stackSection:
            stackSection = descriptionDoc.find_section(stackTitle)
        if stackSection:
            marker = re.compile(r'^<!-- grape-stack: (?P<data>\{.*\}) -->$')
            for line in stackSection.lines:
                match = marker.match(line.strip())
                if match:
                    try:
                        stackMetadata = json.loads(match.group('data'))
                    except ValueError:
                        pass
                    break

        return cls(
            userLines=userDescriptionLines,
            relatedReviews=relatedReviews,
            reviewRules=rules,
            stackMetadata=stackMetadata,
        )

    def to_text(self):
        # Begin with user description
        description = '\n'.join(self.userLines).strip()

        # Add GRAPE section
        if description:
            description += '\n\n# GRAPE'
        else:
            description = '# GRAPE'

        description += f'\n\nGenerated by GRAPE {version.grapeVersion()}.'

        if self.stackMetadata:
            metadata = self.stackMetadata
            description += '\n\n## Stack'
            description += (
                f'\n\n- Stack: `{metadata.get("stack", "unknown")}`'
                f'\n- Level: `{metadata.get("level", "unknown")}`'
                f'\n- Position: {metadata.get("position", "?")} of '
                f'{metadata.get("total", "?")}'
                f'\n- Destination: `{metadata.get("destination", "unknown")}`')
            if metadata.get("depends_on") or metadata.get("parent_source"):
                description += (
                    f'\n- Depends on: '
                    f'{metadata.get("depends_on") or metadata["parent_source"]}')
            if metadata.get("followed_by") or metadata.get("successor_source"):
                description += (
                    f'\n- Followed by: '
                    f'{metadata.get("followed_by") or metadata["successor_source"]}')
            encoded = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
            description += f'\n\n<!-- grape-stack: {encoded} -->'

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
        if link:
            self.relatedReviews.add(link)

    def set_stack_metadata(self, metadata):
        """Replace generated vertical stack relationship metadata."""
        self.stackMetadata = dict(metadata or {})
