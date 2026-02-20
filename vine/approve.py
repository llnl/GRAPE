import logging
import configparser
from datetime import datetime
from io import StringIO
from vine import CodeReviewsFactory
from vine import config_parser_base
from vine import config_parser_global
from vine import config_parser_user
from vine import grapeGit as git
from vine import multi_repo_cmd_launcher
from vine import review
from vine import submodules
from vine import vine_subprocess
from vine.option import Option
from vine.PullRequestDescriptionModel import PullRequestDescriptionModel
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.vine_logging import log_wrapper
from vine import utility
import re
import sys

class Approve(Option, WorkspaceDirHandler):
    """
    grape approve
    Manage approval for a pull/merge request.
    Usage: grape-approve [--rule=<ruleName>]
                         [--source=<topicBranch>]
                         [--target=<publicBranch>]
                         [--project=<prj>]
                         [--repo=<repo>]
                         [--user=<userName>]
                         [--codeReviewsURL=<url>]
                         [--verifySSL=<bool>]
                         [--ssh_pat_url=<url>]
                         [--ssh_pat_port=<int>]

    Options:
        --rule=<ruleName>           The name of the review rule to apply.
        --source=<topicBranch>      The branch to approve the merge request for.
        --target=<publicBranch>     The public branch targeted by the merge request.
                                    Defaults to mapping for source branch.
        --project=<prj>             The top level project (Bitbucket) or group (GitLab) name.
                                    [default: .grapeconfig.project.name]
        --repo=<repo>               The top level repository name.
                                    [default: .grapeconfig.repo.name]
        --user=<userName>           Your GitLab user name.
        --codeReviewsURL=<url>      The code review platform url, e.g. https://your.host.org/gitlab.
                                    [default: .grapeconfig.project.codeReviewsURL]
        --verifySSL=<bool>          Set to False to ignore SSL certificate verification issues.
                                    [default: .grapeconfig.project.verifySSL]
        --ssh_pat_url=<url>         SSH URL for generating Personal Access Tokens to authenticate into a Code Review service's
                                    REST API.
                                    [default: .grapeconfig.repo.ssh_pat_url]
        --ssh_pat_port=<int>        Port number to issue ssh command over to generate a Personal Access Token for authentication
                                    into a Code Review service's REST API.
                                    [default: .grapeconfig.repo.ssh_pat_port]

    """
    def __init__(self):
        super(Approve, self).__init__()
        self._key = "approve"
        self._section = "Code Reviews"

    def description(self):
        return "Approve a merge/pull request."

    @log_wrapper
    def execute(self, args):
        user_name = utility.getUserName(args)
        git_host = utility.authenticateToGitHost(user_name, self.workspace_dir, args)
        top_repo_context = Approve._get_top_repo_context_for_approval(git_host, user_name, args)
        rule = Approve._get_review_rule(top_repo_context, args)
        Approve._approve(user_name, git_host, top_repo_context, rule)

    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_PROJECT)
        config.set(self.SECTION_PROJECT, "codeReviewsURL", "https://your.host.org/gitlab/or/bitbucket")
        config.set(self.SECTION_PROJECT, "verifySSL", "True")
        config.set(self.SECTION_PROJECT, "name", "My unnamed project")
        config.ensureSection(self.SECTION_REPO)
        config.set(self.SECTION_REPO, "ssh_pat_url", "git@gitlab.your.host.org")
        config.set(self.SECTION_REPO, "ssh_pat_port", "7999")
        config.set(self.SECTION_REPO, "name", "My unnamed repo")

    @staticmethod
    def _get_top_repo_context_for_approval(git_host, user_name, args):
        """
        Build and validate the top-level repository context needed for approvals.

        This resolves the project/repo from CLI args, validates the existence of
        the source and target branches, loads the `.grapeconfig` from the source
        branch, and returns a context dictionary used by downstream approval
        logic.

        Parameters
        ----------
        git_host : CodeReviews
            Authenticated code review / git hosting client.
        user_name : str
            Username for git host client
        args : dict
            Parsed command-line arguments. Expected keys:
            - "--project" : str
            - "--repo" : str
            - "--source" : str (optional; may be prompted)
            - "--target" : str (optional; defaults via .grapeconfig mapping)

        Returns
        -------
        dict
            Context containing:
            - project_name
            - repo_name
            - repo
            - source_branch
            - target_branch
            - grape_config (GrapeConfigParserBase)

        Exits
        -----
        Terminates the process with exit code 1 if:
        - source branch does not exist
        - `.grapeconfig` is missing on the source branch
        """
        logging.info(f'Getting top level repository...')

        # Get repo info
        project_name = args['--project']
        repo_name = args['--repo']
        # Get and validate source branch
        source_branch = args["--source"]
        # Get target branch
        target_branch = args['--target']

        if not source_branch:
            print("Open merge requests you are reviewing:")
            repo = git_host.repo(project_name, repo_name)
            Approve._print_open_reviews(repo, user_name, args["--target"])
                        
            source_branch = utility.userInput(f'Please enter the name of the branch being approved: ')

            if not source_branch:
                logging.error(f'GRAPE: ERROR: Source branch is required.')
                exit(1)


        return review.Review._get_top_repo_context(git_host, user_name, project_name, repo_name, source_branch, target_branch)

    @staticmethod
    def _print_open_reviews(repo, user_name, target_branch):
        """
        Prints open merge requests targeting `target_branch` where `user_name`
        has been added using `grape review`. 

        Parameters
        ----------
        repo : Repo
            Repo/project to search
        user_name : str
            User name of the approver.
        target_branch : str or None
            Target branch for merge requests (any target if None)

        """
        for request in repo.pullRequests(target_branch=target_branch):
            descr = request.description()
            description_model = PullRequestDescriptionModel.from_text(descr, None, None, None)

            rules = []

            for rule_label in description_model.reviewRules:
                rule = description_model.reviewRules[rule_label]

                if user_name in rule['reviewers']:
                    rules.append(rule_label)

            if rules:
                print(f"  {request.fromRef()} -> {request.toRef()} [{', '.join(rules)}]")

    @staticmethod
    def _get_review_rule(top_repo_context, args):
        """
        Resolve and validate the active review rule to apply.

        This loads review rules from the repository's `.grapeconfig`, filters to
        active rules, obtains the requested rule name from `args["--rule"]` or
        prompts the user, validates that the rule is active, and returns the rule
        definition.

        Parameters
        ----------
        top_repo_context : dict
            Context dictionary returned by `_get_top_repo_context`, expected to
            include:
            - "grape_config": config_parser_base.GrapeConfigParserBase
        args : dict
            Parsed command-line arguments. Expected key:
            - "--rule": str (optional)

        Returns
        -------
        dict
            The selected review rule definition.

        Exits
        -----
        Terminates the process with exit code 1 if the selected rule name is not
        among the active rules.
        """
        rules = review.parseReviewRules(top_repo_context['grape_config'])
        active_rule_names = [rule_name for rule_name in rules if rules[rule_name].active]

        rule_name = args['--rule']

        if not rule_name:
            rule_name = utility.userInput(f'Please enter a review rule name ({", ".join(active_rule_names)}): ')

        if rule_name not in active_rule_names:
            logging.error(f'GRAPE: ERROR: Review rule "{rule_name}" is invalid. Active rules: {", ".join(active_rule_names)}.')
            exit(1)

        return rules[rule_name]

    @staticmethod
    def _approve(user_name, git_host, top_repo_context, rule):
        """
        Perform the end-to-end approval workflow for a review rule.

        This method:
          1) Validates that `user_name` is eligible to approve `rule`.
          2) Detects which repositories (top repo, submodules, subprojects) have open
             review requests.
          3) Prompts the user for per-repository approval and collects any rule-defined input.
          4) Applies the configured approve actions (e.g., approve, tag, update description)
             to each relevant open review request.

        Parameters
        ----------
        user_name : str
            User name of the approver.
        git_host : CodeReviews
            Authenticated code review / git hosting client.
        top_repo_context : dict
            Context dictionary returned by `_get_top_repo_context`.
        rule : dict
            Review rule definition returned by `_get_review_rule`.

        Side Effects
        ------------
        May prompt the user for input and may update/approve/tag merge/pull requests.

        Exits
        -----
        May terminate the process (via downstream calls) when validation fails or when
        no approvals are granted.
        """
        Approve._validate_approver(user_name, rule)
        modified_repos = review.Review._get_modified_repos(git_host, top_repo_context)
        approve_input = Approve._get_approve_input(rule, user_name, modified_repos)
        Approve._apply_approve_actions(rule, approve_input)

    @staticmethod
    def _validate_approver(user_name, rule):
        """
        Validate that the given user is eligible to approve the provided review rule.

        Parameters
        ----------
        user_name : str
            User name to validate.
        rule : ReviewRule
            Review rule.

        Exits
        -----
        Terminates the process with exit code 1 if the user does not match any
        eligible reviewer pattern.
        """
        if rule.matches_reviewer(user_name):
            return

        logging.error(f'GRAPE: ERROR: User "{user_name}" cannot approve review rule "{rule.name}".')
        exit(1)

    @staticmethod
    def _get_user_input(rule_input):
        # Print prompt
        print(f'\n{rule_input.prompt}')

        # Print help
        help = rule_input.help

        if help:
            print(f'\n  Help:\n    {help}')

        # Print examples
        examples = rule_input.examples

        if examples:
            print('\n  Examples:')

            longest_len = 0

            for example in examples:
                longest_len = max(longest_len, len(example))

            for example, description in examples.items():
                if example:
                    if description:
                        print(f'    "{example}"{" " * (longest_len - len(example))}    {description}')
                    else:
                        print(f'    "{example}"')

        # Print substitutions
        substitutions = rule_input.substitutions

        if substitutions:
            print('\n  Shortcuts/Substitutions:')

            longest_len = 0

            for substitution in substitutions:
                longest_len = max(longest_len, len(substitution))

            for old, new in substitutions.items():
                print(f'    "{old}"{" " * (longest_len - len(old))} -> "{new}"')

        # Print default and prompt for input
        default = rule_input.default

        if default:
            value = input(f'\n(def: {default}) ==> ').strip()
        else:
            value = input('\n==> ').strip()

        # Loop if required and no value was entered
        if rule_input.required:
            while not value:
                print(f'\nPlease enter a non-empty string.')
                value = input('\n==> ').strip()

        # Perform substitutions
        for old, new in substitutions.items():
            value = value.replace(old, new)

        return value

    @staticmethod
    def _get_approve_input(rule, user_name, modified_repos):
        """
        Prompt the user for approvals and collect rule-defined input per modified repository.

        For each repository in `modified_repos`, this method initializes default approval state
        (`approved=False`, `input={}`), checks whether the given `rule` applies to the repo,
        and if so prompts the user to approve the changes on the repo's source
        branch/commit. When approval is granted, it gathers any additional input fields defined
        in `rule["input"]` and stores them in the repo context.

        Parameters
        ----------
        rule : ReviewRule
            Review rule.
        user_name : str
            User name.
        modified_repos : dict
            Mapping of repo_name -> repo_context. Each repo_context is mutated in-place to add:
              - "approved": bool
              - "input": dict

        Returns
        -------
        dict
            The same `modified_repos` mapping with per-repo approval state and collected input.

        Exits
        -----
        Exits with status code 0 when no approvals are granted.
        """
        any_approvals = False
        logging.info(f'Getting approval input for rule "{rule.name}"...')

        for repo_name in modified_repos:
            # Set default approval and input state
            repo_context = modified_repos[repo_name]
            repo_context['approved'] = False
            repo_context['approve_inputs'] = []

            # Check if rule applies
            if not rule.matches_repository(repo_name):
                continue

            # Get review request
            review_request = repo_context['review_request']

            # Prevent author from approving
            if review_request.author() == user_name:
                if not rule.authorEligible:
                    logging.warning(f'GRAPE: WARNING: Merge request author not allowed to approve. Skipping "{repo_name}"...')
                    continue

            # Ask for approval
            source_branch = review_request.fromRef()
            source_commit = review_request.fromSHA().lower()

            print(f'\nRepo: {repo_name}')
            print(f'Branch: {source_branch}')
            print(f'Merge Request: {review_request.link()}')
            print(f'Changes:')

            commits_printed = 0
            max_commits_printed = 5
            short_source_commit = ""
            commits = review_request.commits()

            sorted_commits_desc = sorted(
                commits,
                key=lambda c: datetime.fromisoformat(c.committed_date),
                reverse=True,
            )

            for commit in sorted_commits_desc:
                if commit.id.lower() == source_commit:
                    short_source_commit = commit.short_id.lower()

                dt = datetime.fromisoformat(commit.committed_date)
                local_dt = dt.astimezone()
                formatted_dt = local_dt.strftime("%a %d %b %Y %I:%M %p")

                print(f'  {commit.short_id}    {formatted_dt}    {commit.title}')

                # Limit the number of commits printed
                commits_printed = commits_printed + 1

                if commits_printed == max_commits_printed:
                    break

            if commits_printed == max_commits_printed and len(commits) != max_commits_printed:
                print(f'  ...')

            if not short_source_commit:
                logging.error(f'GRAPE: ERROR: Latest commit "{source_commit}" not found. Contact a GRAPE developer.')
                exit(1)

            approval_granted = utility.userInput(
                'I approve these changes.',
                default='y'
            )

            if not approval_granted:
                logging.info(f'Skipping approval for "{repo_name}"...')
                continue

            if 'tag' in rule.approveActions:
                commit_reviewed = utility.userInput(
                    f'Enter the most recent commit reviewed to confirm approval:'
                ).lower()

                if not source_commit.startswith(commit_reviewed):
                    logging.error(f'GRAPE: ERROR: Reviewed commit sha "{commit_reviewed}" does not match branch head commit sha "{source_commit}". Exiting...')
                    exit(1)

                if not commit_reviewed.startswith(short_source_commit):
                    logging.error(f'GRAPE: ERROR: Reviewed commit sha "{commit_reviewed}" must have at least the same number of characters as the branch head commit short sha "{short_source_commit}". Exiting...')
                    exit(1)

            repo_context['approved'] = True
            any_approvals = True

            # Ask for input
            rule_inputs = rule.approveInputs
            repo_inputs = repo_context['approve_inputs']

            for rule_input in rule_inputs:
                value = None

                if rule_input.value is not None:
                    value = rule_input.value
                else:
                    source = rule_input.source

                    if source == 'commit':
                        value = source_commit
                    elif source == 'username':
                        value = user_name
                    elif source == 'tag':
                        value = f'{rule.name}_{review_request.iid()}'
                    else:
                        value = Approve._get_user_input(rule_input)

                    if rule_input.cache:
                        rule_input.value = value

                repo_inputs.append({
                    'label': rule_input.label,
                    'value': value,
                    'tag': rule_input.tag,
                    'description': rule_input.description
                })

        # Check if any approvals were granted
        if not any_approvals:
            logging.info(f'No merge/pull requests approved. Exiting...')
            exit(0)

        return modified_repos

    @staticmethod
    def _apply_approve_actions(rule, modified_repos):
        """
        Apply rule approval actions to each modified repository.

        When `"description"` is present in `rule.approveActions`, this adds
        and/or overwrites approvals in the pull request description.

        When a repository context is marked approved (`repo_context["approved"] is True`), the
        method also performs any of the following actions configured in `rule.approveActions`:
          - `"approve"`: approve the merge/pull request.
          - `"tag"`: create/update a tag named `{rule.name}_{review_request.iid()}` at the approved source commit,
            with a tag message containing `rule.label` and the collected inputs for that repo.

        Parameters
        ----------
        rule : ReviewRule
        modified_repos : dict
            Mapping of repo_name -> repo_context. Each repo_context is expected to contain:
              - "repo": repository client
              - "review_request": open merge/pull request object
              - "approved": bool
              - "input": dict[str, str]

        Side Effects
        ------------
        May update merge/pull request descriptions; may approve review requests; may create/update tags.

        Raises
        ------
        Exception
            Propagates exceptions thrown by the underlying code review client operations.
        """
        # Build rule section for merge/pull request description
        description = ''

        if 'description' in rule.approveActions:
            # Get the pull request description. All related pull requests
            # should have the same description, so grab the first one.
            for repo_name in modified_repos:
                repo_context = modified_repos[repo_name]
                review_request = repo_context['review_request']
                description = review_request.description()
                break

            # Get the data from the pull request description
            descriptionModel = PullRequestDescriptionModel.from_text(description, None, None, None)

            # Get existing approvals
            reviewRuleModels = descriptionModel.reviewRules

            if rule.label not in reviewRuleModels:
                reviewRuleModels[rule.label] = {
                    'reviewers': set(),
                    'approvals': {}
                }

            approvals = reviewRuleModels[rule.label]['approvals']

            for repo_name in sorted(modified_repos.keys()):
                repo_context = modified_repos[repo_name]

                if repo_context['approved']:
                    # If already approved, overwrite with new approval
                    approvals[repo_name] = {}
                    repo_inputs = repo_context['approve_inputs']

                    for repo_input in repo_inputs:
                        if repo_input['description']:
                            approvals[repo_name][repo_input['label']] = repo_input['value']

            description = descriptionModel.to_text()

        # Now apply approvals. All modified repositories are included because they may need to have their merge request description updated
        for repo_name in modified_repos:
            logging.info(f'Applying approve actions to repository "{repo_name}"...')
            repo_context = modified_repos[repo_name]
            repo = repo_context['repo']
            review_request = repo_context['review_request']

            # Update merge request description
            if 'description' in rule.approveActions:
                logging.info('  Updating merge/pull request description...')
                review_request.update(review_request.version(), description=description)

            if repo_context['approved']:
                # Approve reviewed branch
                if 'approve' in rule.approveActions:
                    logging.info('  Approving merge/pull request...')
                    review_request.approve()

                # Tag reviewed branch
                if 'tag' in rule.approveActions:
                    tag_name = f'{rule.name}_{review_request.iid()}'
                    tag_ref = review_request.fromSHA()
                    tag_message = rule.label

                    repo_inputs = repo_context['approve_inputs']
                    first = True

                    for repo_input in repo_inputs:
                        if repo_input['tag']:
                            if first:
                                tag_message += '\n'
                                first = False

                            tag_message += f'\n* {repo_input["label"]}: {repo_input["value"]}'

                    tag = repo.getTag(tag_name)

                    if tag:
                        logging.info(f'  Replacing tag "{tag_name}"...')
                        tag.delete()
                    else:
                        logging.info(f'  Creating tag "{tag_name}"...')

                    repo.createTag(tag_name, tag_ref, tag_message)
