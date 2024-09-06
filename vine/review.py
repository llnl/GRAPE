import io
import os
import logging
import re
import urllib
from configparser import NoSectionError, NoOptionError
from stashy import errors as stashy_errors
from requests import adapters
from vine import CodeReviewsFactory
from vine import Atlassian
from vine import Gitlab
from vine import config_parser_global
from vine import config_parser_user
from vine import grape_errors
from vine import grapeGit as git
from vine import grapeMenu
from vine import multi_repo_cmd_launcher
from vine import utility
from vine import version
from vine import vine_logging
from vine.option import Option
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.vine_logging import log_wrapper

# Prepare Feature Branch for review
class Review(Option, WorkspaceDirHandler):
    """
    grape review
    Usage: grape-review [--update | --add]
                        [--title=<title>]
                        [--descr=<file> | -m <description>]
                        [--user=<userName> ]
                        [--reviewers=<userNames>]
                        [--source=<topicBranch>]
                        [--target=<publicBranch>]
                        [--state=<openMergedDeclined>]
                        [--codeReviewsURL=<url>]
                        [--verifySSL=<bool>]
                        [--project=<prj>]
                        [--repo=<repo>]
                        [--recurse]
                        [--noRecurse]
                        [--noRecurseSubprojects]
                        [--test]
                        [--prepend | --append]
                        [--subprojectsOnly]
                        [--ssh_pat_url=<url>]
                        [--ssh_pat_port=<int>]
                        [--noLocal | --pushModifiedOnly]
                        [--label_ref=<ref>]
                        [--skiplabels]

    Options:
        --update                    Update an existing pull request with a new description, set of reviewers, etc.
                                    This is the default behavior if a pull request already exists for <topicBranch>
                                    targeting <publicBranch>. If --update is set, and an open pull request doesn't
                                    exist, an error will be generated.
        --add                       Add a new pull request. Default behavior if a pull request doesn't exist for
                                    <topicBranch> targeting <publicBranch>. If a pull request already exists and --add
                                    is set, an error will be generated.
        --title=<title>             The pull request`s title.
        --descr=<file>              A file containing the detailed description of work done on <topicBranch>.
        -m <description>            The pull request description.
        --user=<userName>           Your Bitbucket user name.
        --reviewers=<userNames>     A space- or comma- separate list of reviewers for <topicBranch>
        --source=<topicBranch>      The branch to review. Defaults to current branch.
        --target=<publicBranch>     The branch to publish <topicBranch> to.
                                    Defaults to .grapeconfig.topicPrefixMappings[topicBranchPrefix].
        --state=<state>             The state of the pull request to update. Valid values are open, merged, and
                                    declined.
                                    [default: open]
        --codeReviewsURL=<url>      The code review platform url, e.g. https://your.host.org/gitlab. Grape supports
                                    both Bitbucket and Gitlab code review platforms.
                                    [default: .grapeconfig.project.codeReviewsURL]
        --verifySSL=<bool>          Set to False to ignore SSL certificate verification issues.
                                    [default: .grapeconfig.project.verifySSL]
        --project=<prj>             The project key part of the codeReviews url, e.g. the "GRP" in
                                    https://your.host.org/gitlab/or/bitbucket/projects/GRP/repos/grape/browse.
                                    [default: .grapeconfig.project.name]
        --repo=<repo>               The repo name part of the codeReviews url, e.g. the "grape" in
                                    https://your.host.org/gitlab/or/bitbucket/projects/GRP/repos/grape/browse.
                                    [default: .grapeconfig.repo.name]
        --recurse                   If set, adds a pull request for each modified submodule.
                                    The pull request for the outer level repo will have a description with links to the
                                    submodules' pull requests. On by default if grapeConfig.workspace.manageSubmodules
                                    is set to true.
        --noRecurse                 Disables adding pull requests to submodules.
        --noRecurseSubprojects      Disables adding pull requests to nested subprojects.
        --test                      Uses a dummy version of stashy that requires no communication to an actual Bitbucket
                                    server.
        --prepend                   Prepend <title> to the existing title instead of replacing it.
        --append                    Append <title> to the existing title instead of replacing it.
        --subprojectsOnly           As a work around to when you've only touched a subproject, this will prevent errors
                                    arising in the top level repo.
        --ssh_pat_url=<url>         SSH URL for generating Personal Access Tokens to authenticate into a Code Review service's
                                    REST API.
                                    [default: .grapeconfig.repo.ssh_pat_url]
        --ssh_pat_port=<int>        Port number to issue ssh command over to generate a Personal Access Token for authentication
                                    into a Code Review service's REST API.
                                    [default: .grapeconfig.repo.ssh_pat_port]
        --noLocal                   Do not perform any pushes of the topic branch or any git operations relying on the existence
                                    of the local branch in the local workspace. Branches must still exist on the codeReviews
                                    (Bitbucket, Gitlab) server.
        --pushModifiedOnly          Only push in repos that are modified (compared to the public branch).
                                    By default, the entire local workspace will be pushed to ensure consistency.
                                    In either case, --recurse/--noRecurse/--noRecurseSubprojects arguments are respected.
        --label_ref=<ref>           Reference SHA or branch to use for changedfilelabelmapping. This may be useful to set to a
                                    the merged result SHA to reflect the merged result diff. Defaults to current (source) branch.
        --skiplabels                Skip labeling based on changedfilelabelmapping.


    """
    def __init__(self):
        super(Review, self).__init__()
        self._key = "review"
        self._section = "Code Reviews"

    def description(self):
        return "Prepare current topic branch for review"

    def parseDescriptionArgs(self, args):
        descr = args["-m"]
        if not descr:
            descrFile = args["--descr"]
            if descrFile:
                with io.open(descrFile) as f:
                    descr = f.readlines()
                descr = ''.join(descr)
                for encoding in ['utf-8', 'windows-1252']:
                    try:
                        descr = descr.decode(encoding).encode('ascii','ignore')
                    except:
                        pass
        else:
            # Convert \n to a newline, but only if it is not escaped
            # (alternation allows newline on separate line)
            descr = re.sub('([^\\\\]|)\\\\n', r'\1\n', descr)
            # Remove one backslash from any escaped \n's.
            descr = re.sub('\\\\\\\\n', "\\\\n", descr)
        return descr

    def parseReviewerArgs(self, args):
        reviewers = args["--reviewers"]
        if reviewers is not None:
            reviewers = reviewers.replace(',',' ').split()
        return reviewers

    def buildDescriptionTemplate(self):
        """
        Constructs a template for the merge/pull request description.

        The template includes placeholders for the user description,
        related reviews, and grape data.

        Returns:
            str: A formatted string template with placeholders for:
                - user_description: The user's merge/pull request description.
                - related_reviews: Links to related merge/pull requests.
                - grape_data: Additional data used by GRAPE.
        """

        return '{user_description}\n\n# Related Reviews\n\n{related_reviews}\n\n# GRAPE\n\n{grape_data}'

    def buildDescriptionRegex(self):
        """
        Converts a regex for the merge/pull request description.

        The regex includes capture groups for the user description,
        related reviews, and grape data.

        Returns:
            str: A regex pattern that can be used to match and extract data
            from the merge/pull request description.
        """

        return '(?P<user_description>.*?)\s*# Related Reviews\s*(?P<related_reviews>.*?)\s*# GRAPE\s*(?P<grape_data>.*?)'

    def buildDescription(self, template, data):
        """
        Generates a description by replacing placeholders in the template with
        values from the provided dictionary.

        Args:
            template (str): The template string containing placeholders (in the format `{placeholder}`).
            data (dict): A dictionary containing values to replace in the template.
                         Expected keys: 'user_description', 'related_reviews', and 'grape_data'.

        Returns:
            str: The generated description with placeholders replaced by actual values.

        Example:
            >>> template = '{user_description}\n\n# Related Reviews\n\n{related_reviews}\n\n# GRAPE\n\n{grape_data}'
            >>> data = {'user_description': 'Adds a new feature.', 'related_reviews': 'https://github.com/LLNL/GRAPE/pull/1', 'grape_data': 'v1.49.26'}
            >>> description = self.buildDescription(template, data)
            >>> print(description)
            'Adds a new feature

             # Related Reviews

             https://github.com/LLNL/GRAPE/pull/1

             # GRAPE

             v1.49.26'
        """

        # Start with the description template
        description = template

        # Substitute user description
        userDescription = data.get('user_description', '')
        description = description.replace('{user_description}', userDescription)

        # Substitute related reviews
        relatedReviews = data.get('related_reviews', [])

        if relatedReviews:
            relatedReviews = '  \n'.join(relatedReviews)
        else:
            relatedReviews = 'None'

        description = description.replace('{related_reviews}', relatedReviews)

        # Substitute GRAPE data
        grapeData = data.get('grape_data', '')

        if not grapeData:
            grapeData = version.grapeVersion()

        description = description.replace('{grape_data}', grapeData)

        return description

    def parseDescription(self, description, template):
        """
        Parses a merge/pull request description based on a provided template
        and extracts relevant data.

        This function uses a regex pattern generated from the provided template
        to match and extract specific components from the description. If the
        description does not match the template, it attempts to match an older
        regex pattern. If neither pattern matches, it defaults to treating the
        entire description as the user description.

        Args:
            description (str): The merge/pull request description to be parsed.
            template (str): The template string used to generate the regex pattern for parsing.

        Returns:
            dict: A dictionary containing the parsed data with the following keys:
                - 'user_description': The extracted user description.
                - 'related_reviews': A list of related merge/pull request links extracted from the description (an empty list if none).
                - 'grape_data': Additional data used by GRAPE.

        Example 1:
            >>> template = '{user_description}\n\n# Related Reviews\n\n{related_reviews}\n\n# GRAPE\n\n{grape_data}'
            >>> description = 'Adds a new feature.\n\n# Related Reviews\n\nhttps://github.com/LLNL/GRAPE/pull/1\n\n# GRAPE\n\nv1.49.26'
            >>> result = parseDescription(description, template)
            >>> print(result)
            {'user_description': 'Adds a new feature.', 'related_reviews': ['https://github.com/LLNL/GRAPE/pull/1'], 'grape_data': 'v1.49.26'}

        Example 2:
            >>> template = '{user_description}\n\n# Related Reviews\n\n{related_reviews}\n\n# GRAPE\n\n{grape_data}'
            >>> description = 'Adds a new feature.\n\nThis merge request is related to the merge request at: https://github.com/LLNL/GRAPE/pull/1'
            >>> result = parseDescription(description, template)
            >>> print(result)
            {'user_description': 'Adds a new feature.', 'related_reviews': ['https://github.com/LLNL/GRAPE/pull/1'], 'grape_data': None}

        Notes:
            - The function uses `re.fullmatch` to ensure the entire description matches the regex pattern.
            - If the description does not match the new regex, it falls back to an older regex pattern.
            - If no matches are found, the function defaults to treating the entire description as the user description, with no related reviews or grape data.
        """
        data = {'user_description': '',
                'related_reviews': [],
                'grape_data': ''}

        if not description:
            return data

        regex = self.buildDescriptionRegex()
        match = re.fullmatch(regex, description, re.DOTALL)

        if match:
            data['user_description'] = match.group('user_description')
            data['related_reviews'] = match.group('related_reviews').split()
            if 'None' in data['related_reviews']:
                data['related_reviews'].remove('None')
            data['grape_data'] = match.group('grape_data')
        else:
            oldRegex = f'(?P<user_description>.*?)\s*(?P<related_reviews>({MRLinkText()}\S+\s*)+)'
            match = re.fullmatch(oldRegex, description, re.DOTALL)

            if match:
                data['user_description'] = match.group('user_description')
                data['related_reviews'] = match.group('related_reviews').replace(MRLinkText(), '').split()
                data['grape_data'] = ''
            else:
                logging.warning(f"GRAPE: WARNING: Unexpected format for merge/pull request description. Please check the generated description.")

                data['user_description'] = description
                data['related_reviews'] = []
                data['grape_data'] = ''

        return data


    def getSavedArgs(self, descriptionData):
        """
        Extracts saved arguments from the merge/pull request description.

        :param descriptionData: Data extracted from the merge/pull request description
        :return: A dictionary where keys are argument names and values are argument values
        """
        savedArgs = {}

        if descriptionData:
            grapeData = descriptionData.get('grape_data')

            if grapeData:
                grapeDataLines = grapeData.split('\n')

                for line in grapeDataLines:
                    if line.startswith("--"):
                        tokens = line.split("=")

                        if len(tokens) == 2:
                            savedArgs[tokens[0].strip()] = tokens[1].strip()

        return savedArgs


    def updateArgsFromSavedArgs(self, args, savedArgs):
        '''
        '''
        # Copy current args
        updatedArgs = args

        # Update --reviewers arg
        savedReviewers = self.parseReviewers(savedArgs)
        currentReviewers = self.parseReviewers(args)

        updatedReviewers = savedReviewers
        for reviewRuleName in currentReviewers:
            updatedReviewers[reviewRuleName] = currentReviewers[reviewRuleName]

        newReviewersArg = ''
        for reviewRuleName in updatedReviewers:
            newReviewersArg += f'{reviewRuleName}:{",".join(updatedReviewers[reviewRuleName])}'

        updatedArgs['--reviewers'] = newReviewersArg

        # Return updated args
        return updatedArgs


    def buildGrapeData(self, args):
        '''
        '''
        grapeData = version.grapeVersion()

        if '--reviewers' in args and args['--reviewers']:
            grapeData += f'\n{args["--reviewers"]}'

        return grapeData


    def getDefaultReviewRules(self):
        """
        Retrieves the default review rules for merge/pull requests. The default
        set of review rules is used when no user specified rules are found in
        the global config.

        :return: A dictionary containing the default review rules.
        """
        return {'grape': {'label': Gitlab.GRAPE_GITLAB_APPROVAL_RULE_NAME,
                          'minNumReviewers': 2,
                          'eligibleReviewers': ['.+'],
                          'repositories': ['.+']}}


    def parseReviewRules(self):
        """
        Parses the global GRAPE config file and returns a dictionary of review rules.

        :return: A dictionary where each key is a review rule name and the value is a dictionary representing the rule
        """

        reviewRules = {}

        # Extract the rule names from the [review] section
        config = config_parser_global.grapeConfig()

        if config.has_section(self.SECTION_REVIEW):
            if config.has_option(self.SECTION_REVIEWS, "rules"):
                reviewRuleNames = config.get(self.SECTION_REVIEW, "rules").split()

                for reviewRuleName in reviewRuleNames:
                    sectionName = f"{self.SECTION_REVIEW}-{reviewRuleName}"

                    if not config.has_section(sectionName):
                        logging.error(f"GRAPE: Global config section '{sectionName}' is missing.")
                        exit(1)

                    # Provide a reasonable default for the rule label
                    label = f"GRAPE: {reviewRuleName} review"

                    if config.has_option(sectionName, "label"):
                        label = config.get(sectionName, "label")

                    # Default to one reviewer
                    minNumReviewers = 1

                    if config.has_option(sectionName, "minnumreviewers"):
                        minNumReviewers = config.getint(sectionName, "minnumreviewers")

                    # Default to all reviewers
                    eligibleReviewers = [".+"]

                    if config.has_option(sectionName, "eligiblereviewers"):
                        eligibleReviewers = config.get(sectionName, "eligiblereviewers").split()

                    # Default to all repositories
                    repositories = [".+"]

                    if config.has_option(sectionName, "repositories"):
                        repositories = config.get(sectionName, "repositories").split()

                    # Add the rule
                    reviewRules[reviewRuleName] = {
                        "label": label,
                        "minNumReviewers": minNumReviewers,
                        "eligibleReviewers": eligibleReviewers,
                        "repositories": repositories
                    }

        if not reviewRules:
            reviewRules = self.getDefaultReviewRules()

        return reviewRules


    def parseDefaultReviewRuleName(self, reviewRules):
        """
        Retrieves the default review rule name for merge/pull requests.

        If the user has provided a default in the global config, that is used.
        Otherwise, the name of the first rule is used.

        :param reviewRules: A dictionary containing review rules
        :return: A string containing the default review rule name.
        """
        defaultReviewRuleName = None

        # Extract the rule names from the [review] section
        config = config_parser_global.grapeConfig()

        if config.has_section(self.SECTION_REVIEW):
            if config.has_option(self.SECTION_REVIEW, "defaultrule"):
                defaultReviewRuleName = config.get(self.SECTION_REVIEW, "defaultrule")

                # Check that the default matches one of the review rule names
                if defaultReviewRuleName not in reviewRules:
                    logging.error(f'GRAPE: ERROR: The default review rule name "{defaultReviewRuleName}" does not specify a review rule.')

        if not defaultReviewRuleName:
            for reviewRuleName in reviewRules:
                defaultReviewRuleName = reviewRuleName
                break

        return defaultReviewRuleName


    def parseReviewers(self, args, reviewRules, defaultReviewRuleName):
        '''
        Extracts reviewer groups from the --reviewers argument.
        The argument should consist of whitespace separated groups, where
        each group is in one of the following forms:

        <username>[,<username>]* -> these reviewers are assigned to the default rule
        <rule>:<username>[,<username>] -> these reviewers are assigned to the given rule

        e.g.

        --reviewers="username1,username2 rule1:username1 rule2:username2,username3"

        In this case, username1 and username2 will be assigned to the default
        review rule. username1 will also be assigned to rule1, and username2
        along with username3 will be assigned to rule2.

        :param args: A dictionary containing arguments to a prior or current GRAPE call
        :param reviewRules: A dictionary containing review rules
        :param defaultReviewRuleName A string containing the name of the default rule
        :return: A dictionary where each key is a review rule name and the value is a dictionary containing a label and a unique list of reviewers.
        '''

        reviewers = {}

        # Parse reviewers from saved arguments
        arg = args.get("--reviewers")

        if arg is not None:
            reviewerGroups = arg.split()

            for reviewerGroup in reviewerGroups:
                tokens = reviewerGroup.split(":")

                if len(tokens) == 1:
                    # Use the default rule
                    reviewRuleName = defaultReviewRuleName
                    reviewRuleReviewers = tokens[0].split(',')

                    if reviewRuleName in reviewers:
                        logging.warning(f'GRAPE: WARNING: "Reviewers should be separated by commas instead of whitespace (whitespace is used to separate review rules).')
                        reviewRuleReviewers.extend(reviewers[reviewRuleName]['reviewers'])
                elif len(tokens) == 2:
                    # Use the given rule
                    reviewRuleName = tokens[0]

                    # Check the given rule name is a review rule
                    if reviewRuleName not in reviewRules:
                        logging.error(f'GRAPE: ERROR: "{reviewRuleName}" is not a review rule.')
                        exit(1)

                    reviewRuleReviewers = tokens[1].split(',')

                    if reviewRuleName in reviewers:
                        logging.error(f'GRAPE: WARNING: "{reviewRuleName}" should be specified only once.')
                        reviewRuleReviewers.extend(reviewers[reviewRuleName]['reviewers'])
                else:
                    logging.error(f"GRAPE: ERROR: The --reviewers argument should consist of whitespace separated groups, where each group is in one of the following forms:\n\t<username>[,<username>]*\n\t<rule>:<username>[,<username>]*\n\te.g. --reviewers='username1,username2 rule:username3,username4'")
                    exit(1)

                reviewRule = reviewRules[reviewRuleName]

                # Check for duplicate reviewers
                uniqueReviewRuleReviewers = set(reviewRuleReviewers)

                if len(reviewRuleReviewers) != len(uniqueReviewRuleReviewers):
                    logging.warning(f'GRAPE: WARNING: "{reviewRuleName}" has duplicate reviewers. Duplicates will be removed.')
                    reviewRuleReviewers = list(uniqueReviewRuleReviewers)

                # Check that the reviewers are allowed to approve this rule
                eligibleReviewers = reviewRule["eligibleReviewers"]

                for reviewRuleReviewer in reviewRuleReviewers:
                    validReviewer = False

                    for eligibleReviewer in eligibleReviewers:
                        if re.fullmatch(eligibleReviewer, reviewRuleReviewer):
                            validReviewer = True
                            break

                    if not validReviewer:
                        logging.error(f'GRAPE: ERROR: "{reviewRuleReviewer}" is not an eligible reviewer for review rule "{reviewRuleName}".')
                        exit(1)

                # Check if the minimum number of reviewers has been met
                minNumReviewers = reviewRule["minNumReviewers"]

                if len(reviewRuleReviewers) < minNumReviewers:
                    logging.warning(f"GRAPE: WARNING: {minNumReviewers} reviewer(s) required, but only {len(reviewRuleReviewers)} reviewer(s) given.")

                reviewers[reviewRuleName] = {
                    'label': reviewRule['label'],
                    'reviewers': reviewRuleReviewers
                }

        # Return the dictionary of reviewers
        return reviewers


    @log_wrapper
    def execute(self, args):
        """
        A fair chunk of this stuff relies on stashy's wrapping of the STASH REST API, which is posted at
        https://developer.atlassian.com/static/rest/stash/2.12.1/stash-rest.html
        """
        config = config_parser_global.grapeConfig()
        name = args["--user"]
        if not name:
            name = utility.getUserName()

        logging.info(f"Logging onto {args['--codeReviewsURL']}")
        if args["--test"]:
            codeReviews = Atlassian.TestAtlassian(name)
        else:
            verify = True if args["--verifySSL"].lower() == "true" else False
            codeReviews = CodeReviewsFactory.makeCodeReviews(name, url=args["--codeReviewsURL"],
                                                verify=verify,
                                                port=int(args["--ssh_pat_port"]),
                                                ssh_path = args["--ssh_pat_url"],
                                                workspace_dir=self.workspace_dir
                                                )
        # default project (outer level project)
        project_name = args["--project"]

        # default repo (outer level repo)
        repo_name = args["--repo"]

        # determine source branch and target branch
        branch = args["--source"]
        if not branch:
            branch = git.currentBranch(execution_path=self.workspace_dir)

        #ensure branch is pushed
        if "--noLocal" not in args or not args["--noLocal"]:
            logging.info(f"Pushing {branch} to {codeReviews.url}...")
            git.push(f"origin {branch}", execution_path=self.workspace_dir)
        
        #target branch for outer level repo
        target_branch = args["--target"]
        if not target_branch:
            target_branch = config.getPublicBranchFor(branch)
        # load pull request if it already exists
        wsRepo =  codeReviews.project(project_name).repo(repo_name)
        existingOuterLevelRequest = getReposPullRequest(wsRepo, branch, target_branch, args)

        # determine pull request title
        title = args["--title"]
        if existingOuterLevelRequest is not None and not title:
            title = existingOuterLevelRequest.title()

        #determine pull request URL
        outerLevelURL = None

        if existingOuterLevelRequest:
            outerLevelURL = existingOuterLevelRequest.link()

            if not isinstance(outerLevelURL, str):
                outerLevelURL = outerLevelURL.decode("utf-8")

        # determine pull request description
        descr = self.parseDescriptionArgs(args)

        if not descr and existingOuterLevelRequest:
            pr_description = existingOuterLevelRequest.description()
            if isinstance(pr_description, bytes):
                pr_description = pr_description.decode("utf-8")
            descr = pr_description

        descriptionTemplate = self.buildDescriptionTemplate()
        descriptionData = self.parseDescription(descr, descriptionTemplate)
        savedArgs = self.getSavedArgs(descriptionData)

        # Get review rules
        reviewRules = self.parseReviewRules()
        defaultReviewRuleName = self.parseDefaultReviewRuleName(reviewRules)

        # Determine merge/pull request reviewers
        reviewers = {}

        if existingOuterLevelRequest and existingOuterLevelRequest.reviewers():
            reviewers[defaultReviewRuleName] = {
                'label': reviewRules[defaultReviewRuleName]['label'],
                'reviewers': [r[0] for r in existingOuterLevelRequest.reviewers()]
            }

        reviewers.update(self.parseReviewers(savedArgs, reviewRules, defaultReviewRuleName))
        reviewers.update(self.parseReviewers(args, reviewRules, defaultReviewRuleName))

        newReviewersArg = self.serializeReviewers(reviewers)
        args['--reviewers'] = newReviewersArg

        # Update description
        if outerLevelURL and outerLevelURL not in descriptionData['related_reviews']:
            descriptionData['related_reviews'].append(outerLevelURL)
            descriptionData['related_reviews'].sort()


        #self.updateArgsFromSavedArgs(args, savedArgs)
        descriptionData['grape_data'] = self.buildGrapeData(args)
        updatedDescription = self.buildDescription(descriptionTemplate, descriptionData)

        # Determine pull request reviewers
        reviewers = self.parseReviewers(args)
        self.validateReviewers(reviewers, grapeReviewRules)

        # TODO: Handle the case where --reviewers is not in current or saved args, but the outer level request has reviewers
        #if reviewers is None and existingOuterLevelRequest is not None:
            #reviewers = [r[0] for r in existingOuterLevelRequest.reviewers()]

        # list of description suffixes
        projects_with_reviewer_lists = config.get("publish", "projects_with_reviewer_lists")
        description_suffixes = []
        project_reviewer_lists = {}

        # if we're in append mode, only append what was asked for:
        if args["--append"] or args["--prepend"]:
            title = args["--title"]

        logging.info(f"Updating remote tracking branches for {target_branch}...")

        # Fetch the remote tracking branch for the target branch
        git.fetch(f"origin {target_branch}", execution_path=self.workspace_dir)
        # Skip fetching of remote tracking branch in submodules if no gitlink changes were fetched
        if "--noLocal" in args and args["--noLocal"]:
           submodulesModifiedInOrigin = False
        else:
           submodulesModifiedInOrigin = git.getModifiedSubmodules(self.workspace_dir, "origin/"+target_branch, target_branch)
                     
        upArgs = ['up', f'--public={target_branch}', '--updateRemoteOnly']
        if not submodulesModifiedInOrigin:
           upArgs.extend(['--noRecurse', '--recurseSubprojects'])

        upToDate = grapeMenu.menu().applyMenuChoice('up', upArgs)
        if not upToDate:
            logging.info("Failed to update local branches.")
            return False

        runInSubmodules = not args["--noRecurse"] and (args["--recurse"] or config.getboolean(self.SECTION_WORKSPACE, "manageSubmodules"))
        # assemble description suffixes from any projects with reviewer lists
        if runInSubmodules:
            activeSubmodules = git.getActiveSubmodules(execution_path=self.workspace_dir)
            url_map = git.getAllSubmoduleURLMap(execution_path=self.workspace_dir)
            modifiedSubmodules = git.getModifiedSubmodules(self.workspace_dir, f"origin/{target_branch}", branch, includeAdded=True)
            for submodule in modifiedSubmodules:
                if not submodule:
                    continue
                if submodule in projects_with_reviewer_lists:
                    description_suffix = config.get(f"{submodule}-reviewers", "description_suffix")
                    description_suffix_name = config.get(f"{submodule}-reviewers", "description_suffix_name")
                    description_suffixes.append({"name": description_suffix_name,"body":description_suffix})
        if not args["--noRecurseSubprojects"]:
           nestedProjects = config_parser_user.getAllModifiedNestedSubprojects(
               "origin/"+target_branch, workspaceDir=self.workspace_dir)
           for proj in nestedProjects:
                if proj in projects_with_reviewer_lists:
                    description_suffix = config.get(f"{proj}-reviewers", "description_suffix")
                    description_suffix_name = config.get(f"{proj}-reviewers", "description_suffix_name")
                    description_suffixes.append({"name": description_suffix_name,"body":description_suffix})
        
        # append the description suffixes that aren't already present in the description to the description
        if description_suffixes:
            for suffix in description_suffixes:
                suffix_name = suffix["name"]
                suffix_body = suffix["body"]
                suffix_string = f"{MRBlockDelimiter()}{suffix_name} START{MRBlockDelimiter()}\n{suffix_body}\n{MRBlockDelimiter()}{suffix_name} STOP{MRBlockDelimiter()}"
                if descr:
                    if f"{suffix_name} START" not in descr or f"{suffix_name} STOP" not in descr:
                        descr = f"{descr}\n{suffix_string}"
                else:
                    descr = suffix_string

        # assemble arguments for parallel execution of code reviews
        listOfRepoBranchArgTuples=[]
        ##  Submodule Repos
        if runInSubmodules:
            modifiedSubmodules = git.getModifiedSubmodules(self.workspace_dir, target_branch, branch, includeAdded=True)
            # update target branch based off of branch prefix
            submoduleBranchMappings = config.getMapping(self.SECTION_WORKSPACE, "submoduleTopicPrefixMappings")
            # determine branch prefix
            prefix = git.branchPrefix(branch)
            sub_target_branch = submoduleBranchMappings[prefix]
            for submodule in modifiedSubmodules:
                if not submodule:
                    continue
                changed = False
                if submodule in activeSubmodules:
                    if git.log(f"--oneline origin/{sub_target_branch}..{branch}", execution_path=os.path.join(self.workspace_dir, submodule)):
                        changed = True
                else:
                    url = url_map[submodule]
                    targetHead = f"refs/heads/{sub_target_branch}"
                    branchHead = f"refs/heads/{branch}"
                    remotes = git.lsRemote(f"--heads {git.parseSubprojectRemoteURL(url, execution_path=self.workspace_dir)} {targetHead} {branchHead}", execution_path=self.workspace_dir)
                    targetSHA = None
                    branchSHA = None
        
                    for entry in remotes.splitlines():
                       if entry:
                          SHA_and_ref = entry.split()
                          if SHA_and_ref[1] == targetHead:
                             targetSHA = SHA_and_ref[0]
                          elif SHA_and_ref[1] == branchHead:
                             branchSHA = SHA_and_ref[0]
                          if branchSHA and targetSHA:
                             break
                    if targetSHA and branchSHA and targetSHA != branchSHA:
                       changed = True 

                if changed:
                    submoduleReviewers = {}

                    for reviewRuleName in reviewers:
                        reviewRule = grapeReviewRules[name]
                        reviewRuleRepositoryList = grapeReviewRules["repositories"]

                        for reviewRuleRepository in reviewRuleRepositoryList:
                            if re.fullmatch(reviewRuleRepository, submodule):
                                submoduleReviewers[reviewRuleName] = reviewers[reviewRuleName]

                    reviewer_list = {}
                    if submodule in projects_with_reviewer_lists:
                        reviewer_list_name = config.get(f"{submodule}-reviewers","reviewer_list_name")
                        reviewer_list_reviewers = config.get(f"{submodule}-reviewers","reviewer_list").split()
                        reviewer_list_min_reviewers = config.get(f"{submodule}-reviewers","min_reviewers")
                        reviewer_list = {reviewer_list_name: (reviewer_list_reviewers, reviewer_list_min_reviewers)}
                    listOfRepoBranchArgTuples.append((submodule,branch,[{"codeReviews":codeReviews,
                                                                         "isSubmodule": True,
                                                                         "isNested": False,
                                                                         "args": args,
                                                                         "target_branch": sub_target_branch,
                                                                         "descr": updatedDescription,
                                                                         "title": title,
                                                                         "proj": submodule,
                                                                         "outerLevelURL": outerLevelURL,
                                                                         "reviewers": submoduleReviewers,
                                                                         "reviewer_list" : reviewer_list,
                                                                         "active": submodule in activeSubmodules }]))
                    project_reviewer_lists.update(reviewer_list)

        ## NESTED SUBPROJECT REPOS
        if not args["--noRecurseSubprojects"]:
           activeNestedSubprojects = config_parser_user.getAllActiveNestedSubprojects(workspaceDir=self.workspace_dir)
           nestedProjects = config_parser_user.getAllModifiedNestedSubprojects(
               "origin/"+target_branch, now=branch, workspaceDir=self.workspace_dir, checkRemote=True)
           nestedProjectPrefixes = [config.get(f"nested-{name}", "prefix") for name in nestedProjects]

           for proj, prefix in zip(nestedProjects, nestedProjectPrefixes):
               subprojectReviewers = {}

               for reviewRuleName in reviewers:
                   grapeReviewRule = grapeReviewRules[reviewRuleName]
                   reviewRuleRepositoryList = grapeReviewRule["repositories"]

                   for reviewRuleRepository in reviewRuleRepositoryList:
                       if re.fullmatch(reviewRuleRepository, proj):
                           subprojectReviewers[reviewRuleName] = reviewers[reviewRuleName]

               reviewer_list = {}
               if proj in projects_with_reviewer_lists:
                   reviewer_list_name = config.get(f"{proj}-reviewers","reviewer_list_name")
                   reviewer_list_reviewers = config.get(f"{proj}-reviewers","reviewer_list").split()
                   reviewer_list_min_reviewers = config.get(f"{proj}-reviewers","min_reviewers")
                   reviewer_list = {reviewer_list_name: (reviewer_list_reviewers, reviewer_list_min_reviewers)}
               prefix_path = os.path.join(self.workspace_dir, prefix)
               listOfRepoBranchArgTuples.append((prefix_path,branch,[{"codeReviews":codeReviews,
                                                                    "isSubmodule": False,
                                                                    "isNested": True,
                                                                    "args": args,
                                                                    "target_branch": target_branch,
                                                                    "descr": updatedDescription,
                                                                    "title": title,
                                                                    "proj": proj,
                                                                    "outerLevelURL": outerLevelURL,
                                                                    "reviewers": subprojectReviewers,
                                                                    "reviewer_list" : reviewer_list,
                                                                    "active": proj in activeNestedSubprojects}]))
               project_reviewer_lists.update(reviewer_list)


        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(PostPullRequestForRepo, listOfRepoBranchArgTuples=listOfRepoBranchArgTuples, workspace_dir=self.workspace_dir)
        pullRequestLinks = launcher.launchFromWorkspaceDir(noPause=True, handleMRE=HandlePostPullRequestForRepoMRE)

        ## OUTER LEVEL REPO
        # load the repo level REST resource
        if not args["--subprojectsOnly"]:
            if "--noLocal" in args and args["--noLocal"]:
                pass
            else:
                if not git.hasBranch(branch, execution_path=self.workspace_dir):
                    logging.info(
                        f"Top level repository does not have a branch {branch}," +
                        " not generating a Pull Request")
                    return True
                if git.branchUpToDateWith(target_branch, branch, execution_path=self.workspace_dir):
                    logging.info(
                        f"{target_branch} up to date with {branch}," +
                        " not generating a Pull Request in Top Level repo")
                    return True
                if not git.log(f"--oneline origin/{target_branch}..{branch}", execution_path=self.workspace_dir):
                    logging.info(
                        f"{branch} is in the history of {target_branch}," +
                        " not generating a Pull Request in Top Level repo")
                    return True

            add_labels = []
            remove_labels = []
            if not args["--skiplabels"]:
               try:
                  changedfilelabelmapping = config.getMapping(self.SECTION_REVIEW, "changedfilelabelmapping")
                  if changedfilelabelmapping:
                      label_ref = args["--label_ref"]
                      if not label_ref:
                          label_ref = branch
                      # find the common ancestor between the reference for labels and the target branch
                      mergeBase = git.mergeBase(f"{target_branch} {label_ref}", execution_path=self.workspace_dir)
                      for path,label in changedfilelabelmapping.items():
                          try:
                             # check if the file has changes from the ancestor
                             if git.diff(f"--name-only {label_ref} {mergeBase} {path}", execution_path=self.workspace_dir):
                                 add_labels.append(label)
                             else:
                                 remove_labels.append(label)
                          except grape_errors.GrapeGitError:
                             logging.warning(f"GRAPE: WARNING: .grapeconfig [review] changedfilelabelmapping, '{path}' not found, ignoring...")
               except NoSectionError:
                  pass
               except NoOptionError:
                  pass

            repo_name = args["--repo"]
            repo = CodeReviewsFactory.repoObject(codeReviews, repoName=repo_name, projectName=project_name)
            logging.info(f"Posting pull request to {project_name},{repo_name}")

            outerReviewers = {}

            for reviewRuleName in reviewers:
                reviewRule = grapeReviewRules[reviewRuleName]
                reviewRuleRepositoryList = reviewRule["repositories"]

                for reviewRuleRepository in reviewRuleRepositoryList:
                    if re.fullmatch(reviewRuleRepository, repo_name):
                        outerReviewers[reviewRuleName] = reviewers[reviewRuleName]

            request = postPullRequest(repo, title, branch, target_branch, updatedDescription, reviewers, project_reviewer_lists, args, self.workspace_dir, add_labels=add_labels, remove_labels=remove_labels)

            # Update related reviews
            outerLevelURL = request.link()
            if not isinstance(outerLevelURL, str):
                outerLevelURL = outerLevelURL.decode("utf-8")

            if runInSubmodules and not args["--noRecurseSubprojects"]:
                # Ignore related review links scraped from the outer level
                # merge/pull request description. Then add all the new
                # submodule/subproject links. Only add the outer level link
                # if there are any submodule/subproject links.
                updatedReviewLinks = []

                for link in pullRequestLinks:
                    if not isinstance(link, str):
                        link = link.decode("utf-8")

                    updatedReviewLinks.append(link)

                if updatedReviewLinks:
                    updatedReviewLinks.append(outerLevelURL)
            else:
                # Start with related review links scraped from the outer level
                # merge/pull request description. Then add all the new links if
                # they are not already in the list.
                updatedReviewLinks = descriptionData['related_reviews']

                for link in pullRequestLinks:
                    if not isinstance(link, str):
                        link = link.decode("utf-8")

                    if link not in updatedReviewLinks:
                        updatedReviewLinks.append(link)

                if outerLevelURL not in updatedReviewLinks:
                    updatedReviewLinks.append(outerLevelURL)

            updatedReviewLinks.sort()

            descriptionData['related_reviews'] = updatedReviewLinks

            updatedDescription = self.buildDescription(descriptionTemplate, descriptionData)

            pre_update_description = request.description()
            if isinstance(pre_update_description, bytes):
                pre_update_description = pre_update_description.decode("utf-8")
            if updatedDescription != pre_update_description:
                request = postPullRequest(repo, title, branch, target_branch,
                                          updatedDescription,
                                          outerReviewers,
                                          project_reviewer_lists,
                                          args,
                                          self.workspace_dir,
                                          add_labels=add_labels, remove_labels=remove_labels)

            logging.info(f"Request generated/updated:\n\n{request}")

        if ("--pushModifiedOnly" not in args or not args["--pushModifiedOnly"]) and ("--noLocal" not in args or not args["--noLocal"]):
            logging.info(f"Pushing {branch} from workspace (use --pushModifiedOnly/--noLocal to skip this step)...")
            
            # top level was already pushed at the beginning
            pushArgs = ['push', '--noTopLevel']
            if not runInSubmodules:
                pushArgs.append('--noRecurse')
            if args["--noRecurseSubprojects"]:
                pushArgs.append('--noRecurseSubprojects')

            pushed = grapeMenu.menu().applyMenuChoice("push", pushArgs)
            if not pushed:
                return False
        return True


    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_PROJECT)
        config.set(self.SECTION_PROJECT, "codeReviewsURL", "https://your.host.org/gitlab/or/bitbucket")
        config.set(self.SECTION_PROJECT, "verifySSL", "True")
        config.set(self.SECTION_PROJECT, "name", "My unnamed project")
        config.set(self.SECTION_REPO, "ssh_pat_url", "git@gitlab.your.host.org")
        config.set(self.SECTION_REPO, "ssh_pat_port", "7999")


def MRLinkText():
    return "This merge request is related to the merge request at: "


def MRBlockDelimiter():
    return "--------------------"


def HandlePostPullRequestForRepoMRE(mre):
    for e, repo, branch in zip(mre.exceptions(), mre.repos(), mre.branches()):
        raise e


def PostPullRequestForRepo(repo, branch, args, *, workspace_dir):
    kwargs = args[0]
    codeReviews = kwargs["codeReviews"]
    isSubmodule = kwargs["isSubmodule"]
    isNested = kwargs["isNested"]
    review_args = kwargs["args"]
    target_branch = kwargs["target_branch"]
    descr = kwargs["descr"]
    title = kwargs["title"]
    proj = kwargs["proj"]
    outerLevelURL = kwargs["outerLevelURL"]
    reviewers = kwargs["reviewers"]
    reviewer_list  = kwargs["reviewer_list"]
    active = kwargs["active"]

    # push branch
    if active and ("--noLocal" not in review_args or ("--noLocal" in review_args and not review_args["--noLocal"])):
        logging.info(f"Pushing {branch} to {codeReviews.url} in {repo}")
        git.push(f"origin {branch}", execution_path=repo)

    if isNested:
        codeReview_repo = CodeReviewsFactory.repoFromNestedSubprojectName(codeReviews, proj)
    elif isSubmodule:
        codeReview_repo = CodeReviewsFactory.repoFromSubmodulePath(codeReviews, proj)
    else:
        codeReview_repo = CodeReviewsFactory.repoObject(codeReviews)

    #amend the subproject pull request description with the link to the outer pull request
    getReposPullRequestDescription(codeReview_repo, branch, target_branch, review_args)

    newRequest = postPullRequest(codeReview_repo, title, branch, target_branch, descr, reviewers, reviewer_list, review_args, repo)
    if newRequest:
        return newRequest.link()
    else:
        return ""


def getReposPullRequest(repo, branch, target_branch, args):
    pull_requests = repo.pullRequests(direction="OUTGOING", at=f"refs/heads/{branch}", state=args["--state"])
    # check to see if pull request already exists for this branch
    request = None
    for rqst in pull_requests:
        if rqst.toRef() == target_branch and rqst.fromRef() == branch:
            request = rqst
            break
    return request


def getReposPullRequestDescription(repo, branch, target_branch, args):
    descr = None
    request = getReposPullRequest(repo, branch, target_branch, args)
    if request is not None:
        descr = request.description()
        if isinstance(descr, bytes):
            descr = descr.decode("utf-8")
    return descr


def pullRequestAlreadyMerged(errorMessage):
    if "already up-to-date with branch" in errorMessage or \
            "This pull request has already been merged" in errorMessage:
        return True
    return False


def targetBranchMissing(errorMessage):
    if "Repository" in errorMessage and "of project with key" in errorMessage and "has no branch" in errorMessage:
        return True
    return False


def postPullRequest(repo, title, branch, target_branch, descr, reviewers, reviewer_list, args, git_execution_path,
                    add_labels=[], remove_labels=[]):
    config = config_parser_global.grapeConfig()
    repo_name = repo.project.name


    # get the open pull requests outgoing from our public branch
    logging.info(f"Gathering active pull requests on {branch} for repo {args['--repo']}")
    request = getReposPullRequest(repo, branch, target_branch, args)

    if not request:
        if not args["--update"]:
            # add a new pull request
            if not title:
                title = branch
            try:
                logging.info(
                    f"Creating new pull request titled '{title}' " + "\n" +
                    f" for branch {branch} targeting {target_branch}. ")
                logging.info(f"reviewers: {reviewers}, labels={add_labels}")
                request = repo.createPullRequest(title, branch, target_branch, description=descr, reviewers=reviewers,
                                                 labels=add_labels)
                if request:
                   url = request.link()
                   logging.info(f"Pull request created at {url} .")
            except stashy_errors.GenericException as e:
                logging.error(f"BITBUCKET: {e.data['errors'][0]['message']}")
                if not pullRequestAlreadyMerged(e.data["errors"][0]["message"]):
                    exit(1)
            except stashy_errors.NotFoundException as e:
                if targetBranchMissing(e.data["errors"][0]["message"]):
                    if utility.userInput(f"Target branch {target_branch} in {git_execution_path} is missing ... would you like to create and push it? [y/n]"):
                        start_branch = utility.userInput(f"Where should {target_branch} branch off of?")
                        git.branch(f"{target_branch} {start_branch}", execution_path=git_execution_path)
                        git.push(f"origin {target_branch}", execution_path=git_execution_path)
                        postPullRequest(repo, title, branch, target_branch, descr, reviewers, reviewer_list, args, git_execution_path,
                                        add_labels=add_labels, remove_labels=remove_labels)
        else:
            logging.info(
                f"No pull request from {branch} to {target_branch} to update")

    else:
        if not args["--add"]:
            # update the pull request
            logging.info("Updating pull request...")
            try:
                #if not reviewers:
                #    reviewers = [r[0] for r in request.reviewers()]
                # Remove duplicate reviewers
                #reviewers = list(set(reviewers))
                logging.info(f"reviewer list is: {reviewers}")
                ver = request.version()

                if title is not None and (args["--prepend"] or args["--append"]):
                    currentTitle = request.title()
                    if args["--prepend"]:
                        if currentTitle.startswith(title):
                            title = currentTitle
                        else:
                            title = title + currentTitle
                    elif args["--append"]:
                        if currentTitle.endswith(title):
                            title = currentTitle
                        else:
                            title = currentTitle + title

                author = request.author()
                subReviewers = reviewers.copy()

                for reviewRuleName in subReviewers:
                    ruleReviewers = subReviewers[reviewRuleName]

                    if author in ruleReviewers:
                        logging.info(
                                f"{author} is the author of the pull" +
                                " request and cannot be a reviewer")
                        subReviewers[reviewRuleName].remove(author)

                if title is not None or descr is not None or subReviewers or add_labels or remove_labels:
                    logging.info(
                        f"updating request with title={title}, " +
                        f"description={descr}, reviewers={subReviewers}, add_labels={add_labels}, remove_labels={remove_labels}")
                    if "gitlab" in args["--codeReviewsURL"]:
                       combined_reviewers = {Gitlab.GRAPE_GITLAB_APPROVAL_RULE_NAME:(subReviewers, len(subReviewers) if subReviewers else 0)}
                       combined_reviewers.update(reviewer_list)
                       request = request.update(ver, title=title,  description=descr, reviewers=combined_reviewers, add_labels=add_labels, remove_labels=remove_labels)
                    else:
                       request = request.update(ver, title=title,  description=descr, reviewers=subReviewers, add_labels=add_labels, remove_labels=remove_labels)
                    if add_labels or remove_labels:
                       logging.info("Regenerating pipeline...")
                       request.regeneratePipeline()
                    url = request.link()
                    logging.info(f"Pull request updated at {url} .")
                else:
                    url = request.link()
                    logging.info(f"Pull request unchanged at {url} .")
            except stashy_errors.GenericException as e:
                logging.error(f"BITBUCKET: {e.data['errors'][0]['message']}")
                logging.error(f"BITBUCKET: {e.data}")
                if not pullRequestAlreadyMerged(e.data["errors"][0]["message"]):
                    exit(1)
        else:
            logging.info(f"BITBUCKET: Pull request from {branch} to " +
                         f"{target_branch} already exists, can't add a new one")

    return request


if __name__ == "__main__":
    grapeMenu.menu().applyMenuChoice("review",[])
