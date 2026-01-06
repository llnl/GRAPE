import re

def parse_gitmodules(contents):
    """
    Parse the contents of a .gitmodules file and extract submodule information.

    Args:
        contents (iterable of str): Iterable of lines from a .gitmodules file.
            Each line should be a string.

            Example:
                '''
                [submodule "libA"]
                    path = libs/libA
                    url = https://github.com/example/libA.git
                    branch = main

                [submodule "libB"]
                    path = libs/libB
                    url = https://github.com/example/libB.git
                '''.splitlines()

    Returns:
        dict: A dictionary mapping submodule names to their information.
            Each submodule is represented as a dictionary of key-value pairs.

            Example:
                {
                    "libA": {
                        "path": "libs/libA",
                        "url": "https://github.com/example/libA.git",
                        "branch": "main"
                    },
                    "libB": {
                        "path": "libs/libB",
                        "url": "https://github.com/example/libB.git"
                    }
                }

    Notes:
        - Ignores lines outside submodule sections and malformed lines.

    """
    # Regex for parsing section headers: [submodule "submodule/name"]
    submodule_header_pattern = re.compile(r'\[submodule\s+"([^"]+)"\s*\]')

    # Regex for parsinng key-value pairs: key = value
    key_value_pattern = re.compile(r'([a-zA-Z][a-zA-Z0-9-]*)\s*=\s*(.+)$')

    submodules = {}
    current_submodule = None

    for line in contents:
        line = line.strip()

        # Check for a new submodule section
        submodule_header_match = submodule_header_pattern.match(line)

        if submodule_header_match:
            # Get the name of the submodule
            current_submodule = submodule_header_match.group(1)
            submodules[current_submodule] = {}
        elif current_submodule:
            # Check for a key-value pair
            key_value_match = key_value_pattern.match(line)

            if key_value_match:
                key, value = key_value_match.groups()
                submodules[current_submodule][key] = value

    return submodules
