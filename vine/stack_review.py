"""Review submission orchestration for a linear branch stack."""

import json
import logging

from vine import grapeMenu
from vine.stack import IntegrationTargetResolver, StackError


class StackReviewer:
    """Submit each stack level to its immediate integration target."""

    def __init__(self, workspace_dir, manifest):
        self.workspace_dir = workspace_dir
        self.manifest = manifest

    def _levels(self, from_level=None):
        start = self.manifest.index(from_level) if from_level else 0
        return list(enumerate(self.manifest.levels[start:], start=start))

    def plan(self, from_level=None):
        """Print the vertical review chain and return planned levels."""
        resolver = IntegrationTargetResolver(self.manifest)
        levels = self._levels(from_level)
        logging.info(f"Stack {self.manifest.name}: review plan")
        for position, level in levels:
            logging.info(
                f"  {position + 1}. {level.branch} -> {resolver.target(level.id)}")
        return levels

    def run(self, from_level=None, dry_run=False, no_local=False,
            no_recurse=False, no_recurse_subprojects=False,
            draft_descendants=True, print_comments=False,
            ignore_commenters=None):
        """Create/update reviews from bottom to top using ``grape review``."""
        levels = self.plan(from_level)
        if dry_run:
            return True
        resolver = IntegrationTargetResolver(self.manifest)
        for position, level in levels:
            target = resolver.target(level.id)
            parent_level = self.manifest.levels[position - 1] if position else None
            next_level = (
                self.manifest.levels[position + 1]
                if position + 1 < len(self.manifest.levels) else None)
            metadata = {
                "stack_id": self.manifest.id,
                "stack": self.manifest.name,
                "level_id": level.id,
                "level": level.name,
                "position": position + 1,
                "total": len(self.manifest.levels),
                "destination": self.manifest.destination,
                "parent_source": parent_level.branch if parent_level else None,
                "parent_target": (
                    resolver.target(parent_level.id) if parent_level else None),
                "successor_source": next_level.branch if next_level else None,
            }
            review_args = [
                f"--source={level.branch}",
                f"--target={target}",
                "--stackMetadata=" + json.dumps(metadata, separators=(",", ":")),
            ]
            if no_local or print_comments:
                review_args.append("--noLocal")
            if no_recurse:
                review_args.append("--noRecurse")
            if no_recurse_subprojects:
                review_args.append("--noRecurseSubprojects")
            if draft_descendants and position > 0 and not print_comments:
                review_args.append("--draft")
            if print_comments:
                review_args.append("--printUnresolvedComments")
                for commenter in ignore_commenters or []:
                    review_args.append(f"--ignoreCommenter={commenter}")
            result = grapeMenu.menu(workspace_dir=self.workspace_dir).applyMenuChoice(
                "review", review_args)
            if not result:
                raise StackError(
                    f"Review operation failed at level {level.name!r}.")
        return True
