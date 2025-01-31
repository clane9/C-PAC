import os
import re
import yaml
from click import BadParameter
from datetime import datetime
from CPAC.utils.configuration import Configuration, DEFAULT_PIPELINE_FILE
from CPAC.utils.utils import dct_diff, load_preconfig, lookup_nested_value, \
    update_config_dict, update_pipeline_values_1_8


def create_yaml_from_template(
    d, template=DEFAULT_PIPELINE_FILE, include_all=False
):
    """Save dictionary to a YAML file, keeping the structure
    (such as first level comments and ordering) from the template

    It may not be fully robust to YAML structures, but it works
    for C-PAC config files!

    Parameters
    ----------
    d : dict or Configuration

    template : str
        path to template or name of preconfig

    include_all : bool
        include every key, even those that are unchanged

    Examples
    --------
    >>> import yaml
    >>> from CPAC.utils.configuration import Configuration
    >>> Configuration(yaml.safe_load(create_yaml_from_template({}))).dict(
    ...     ) == Configuration({}).dict()
    True
    >>> Configuration(yaml.safe_load(create_yaml_from_template({},
    ...     template='Lil BUB')))
    Traceback (most recent call last):
        ...
    ValueError: 'Lil BUB' is not a valid path nor a defined preconfig.
    """  # noqa: E501 # pylint: disable=line-too-long
    def _count_indent(line):
        '''Helper method to determine indentation level

        Parameters
        ----------
        line : str

        Returns
        -------
        number_of_indents : int

        Examples
        --------
        >>> _count_indent('No indent')
        0
        >>> _count_indent('    Four spaces')
        2
        '''
        return (len(line) - len(line.lstrip())) // 2

    def _create_import_dict(diff):
        '''Method to return a dict of only changes given a nested dict
        of (dict1_value, dict2_value) tuples

        Parameters
        ----------
        diff : dict
            output of `dct_diff`

        Returns
        -------
        dict
            dict of only changed values

        Examples
        --------
        >>> _create_import_dict({'anatomical_preproc': {
        ...     'brain_extraction': {'extraction': {
        ...         'run': ([True], False),
        ...         'using': (['3dSkullStrip'], ['niworkflows-ants'])}}}})
        {'anatomical_preproc': {'brain_extraction': {'extraction': {'run': False, 'using': ['niworkflows-ants']}}}}
        '''  # noqa: E501  # pylint: disable=line-too-long
        if isinstance(diff, tuple) and len(diff) == 2:
            return diff[1]
        if isinstance(diff, dict):
            i = {}
            for k in diff:
                try:
                    j = _create_import_dict(diff[k])
                    if j != {}:
                        i[k] = j
                except KeyError:
                    continue
            return i
        return diff

    def _format_key(key, level):
        '''Helper method to format YAML keys

        Parameters
        ----------
        key : str
        level : int

        Returns
        -------
        yaml : str

        Examples
        --------
        >>> _format_key('base', 0)
        '\nbase: '
        >>> _format_key('indented', 2)
        '\n    indented:'
        '''
        return f'\n{" " * level * 2}{key}: '

    def _format_list_items(l,  # noqa: E741  # pylint:disable=invalid-name
                           line_level):
        '''Helper method to handle lists in the YAML

        Parameters
        ----------
        l : list

        line_level : int

        Returns
        -------
        yaml : str

        Examples
        --------
        >>> _format_list_items([1, 2, {'nested': 3}], 0)
        '  - 1\n  - 2\n  - nested: 3'
        >>> _format_list_items([1, 2, {'nested': [3, {'deep': [4]}]}], 1)
        '    - 1\n    - 2\n    - nested:\n      - 3\n      - deep:\n        - 4'
        '''  # noqa: E501  # pylint: disable=line-too-long
        # keep short, simple lists in square brackets
        if all(isinstance(item, (str, bool, int, float)) for item in l):
            if len(str(l)) < 50:
                return str(l).replace("'", '').replace('"', '')
        # list long or complex lists on lines with indented '-' lead-ins
        return '\n' + '\n'.join([
            f'{indent(line_level)}{li}' for li in yaml.dump(
                yaml_bool(l)
            ).replace("'On'", 'On').replace("'Off'", 'Off').split('\n')
        ]).rstrip()

    # set starting values
    output = ''
    comment = ''
    space_match = r'^\s+.*'
    level = 0
    nest = []
    list_item = False
    list_level = 0
    line_level = 0
    template_name = template
    if isinstance(d, Configuration):
        d = d.dict()
    try:
        template = load_preconfig(template)
    except BadParameter as bad_parameter:
        if 'default' in template.lower():
            template = DEFAULT_PIPELINE_FILE
        if not os.path.exists(template) or os.path.islink(template):
            raise ValueError(f'\'{template_name}\' is not a valid path nor a '
                             'defined preconfig.') from bad_parameter
    template_included = False

    # load default values
    d_default = Configuration(yaml.safe_load(open(template, 'r'))).dict()

    if (
        template == DEFAULT_PIPELINE_FILE or
        not dct_diff(
            yaml.safe_load(open(DEFAULT_PIPELINE_FILE, 'r')), d_default)
    ):
        template_name = 'default'

    # update values
    if include_all:
        d_default.update(d)
        d = _create_import_dict(dct_diff({}, d_default))
    else:
        d = _create_import_dict(dct_diff(d_default, d))

    # generate YAML from template with updated values
    template_dict = yaml.safe_load(open(template, 'r'))
    with open(template, 'r') as f:
        for line in f:

            # persist comments and frontmatter
            if line.startswith('%') or line.startswith('---') or re.match(
                r'^\s*#.*$', line
            ):
                list_item = False
                line = line.strip('\n')
                comment += f'\n{line}'
            elif len(line.strip()):
                if re.match(space_match, line):
                    line_level = _count_indent(line)
                else:
                    line_level = 0

                # handle lists as a unit
                if list_item:
                    if line_level < list_level - 1:
                        list_item = False
                        level = list_level
                        list_level = 0
                elif line.lstrip().startswith('-'):
                    list_item = True
                    list_level = line_level - 1

                else:
                    # extract dict key
                    key_group = re.match(
                        r'^\s*(([a-z0-9A-Z_]+://){0,1}'
                        r'[a-z0-9A-Z_/][\sa-z0-9A-Z_/\.-]+)\s*:', line)
                    if key_group:
                        if not template_included:
                            # prepend comment from template
                            if len(comment.strip()):
                                comment = re.sub(
                                    r'(?<=# based on )(.* pipeline)',
                                    f'{template_name} pipeline',
                                    comment
                                )
                                output += comment
                                output += f'\nFROM: {template_name}\n'
                                comment = ''
                            template_included = True
                        key = key_group.group(1).strip()

                        # calculate key depth
                        if line_level == level:
                            if level > 0:
                                nest = nest[:-1] + [key]
                            else:
                                nest = [key]
                        elif line_level == level + 1:
                            nest += [key]
                        elif line_level < level:
                            nest = nest[:line_level] + [key]

                        # only include updated and new values
                        try:
                            # get updated value for key
                            value = lookup_nested_value(d, nest)
                            orig_value = lookup_nested_value(d_default, nest)
                            # Use 'On' and 'Off' for bools
                            if (isinstance(orig_value, bool) or (
                                isinstance(orig_value, str) and
                                orig_value in {'On', 'Off'}
                            ) or (isinstance(orig_value, list) and all([(
                                isinstance(orig_item, bool) or (
                                    isinstance(orig_item, str) and
                                    orig_item in {'On', 'Off'}
                                )
                            ) for orig_item in orig_value])
                            )):
                                value = yaml_bool(value)
                            # prepend comment from template
                            if len(comment.strip()):
                                output += comment
                            else:
                                output += '\n'

                            # write YAML
                            output += _format_key(key, line_level)
                            if isinstance(value, list):
                                output += _format_list_items(
                                    value, line_level)
                            elif isinstance(value, dict):
                                for k in value.keys():
                                    try:
                                        lookup_nested_value(template_dict,
                                                            nest + [k])
                                    # include keys not in template
                                    except KeyError:
                                        output += _format_key(
                                            k, line_level + 1)
                                        parsed = _format_list_items(
                                            value[k],
                                            line_level + 1
                                        ) if isinstance(
                                            value[k], list) else yaml_bool(
                                                value[k])
                                        if isinstance(parsed, (int, float)):
                                            parsed = str(parsed)
                                        elif parsed is None:
                                            parsed = ''
                                        output += parsed if (
                                            isinstance(parsed, str)
                                        ) else (
                                            '\n' + indent(line_level + 1) +
                                            f'\n{indent(line_level + 1)}' +
                                            yaml.dump(parsed) + '\n')
                            else:
                                output += str(value)
                        except KeyError:
                            # clear comment for excluded key
                            comment = '\n'

                        # reset variables for loop
                        comment = '\n'
                        level = line_level
            elif len(comment) > 1 and comment[-2] != '\n':
                comment += '\n'
    while '\n\n\n' in output:
        output = output.replace('\n\n\n', '\n\n')
    return output.lstrip('\n').replace('null', '')


def indent(line_level):
    '''Function to return an indent string for a given level

    Parameters
    ----------
    line_level : int
        The level of indentation to return

    Returns
    -------
    str
        The string of spaces to use for indentation
    '''
    return " " * (2 * line_level + 2)


def yaml_bool(value):
    '''Helper function to give On/Off value to bools

    Parameters
    ----------
    value : any

    Returns
    -------
    value : any

    Examples
    --------
    >>> yaml_bool(True)
    'On'
    >>> yaml_bool([False, 'On', True])
    ['Off', 'On', 'On']
    '''
    yaml_lookup = {
        True: 'On', 'True': 'On', 1: 'On',
        False: 'Off', 'False': 'Off', 0: 'Off'}
    if (
        isinstance(value, bool) or isinstance(value, str)
    ) and value in yaml_lookup:
        return yaml_lookup[value]
    elif isinstance(value, list):
        return [yaml_bool(item) for item in value]
    elif isinstance(value, dict):
        return {k: yaml_bool(value[k]) for k in value}
    return value


def upgrade_pipeline_to_1_8(path):
    '''Function to upgrade a C-PAC 1.7 pipeline config to C-PAC 1.8

    Parameters
    ----------
    path : str

    Returns
    -------
    None

    Outputs
    -------
    {path}.{now}.bak
        original file

    path
        upgraded file
    '''
    # back up original config
    now = datetime.isoformat(datetime.now()).replace(':', '_')
    backup = f'{path}.{now}.bak'
    print(f'Backing up {path} to {backup} and upgrading to C-PAC 1.8')
    original = open(path, 'r').read()
    open(backup, 'w').write(original)
    # upgrade and overwrite
    orig_dict = yaml.safe_load(original)
    # set Regressor 'Name's if not provided
    regressors = orig_dict.get('Regressors')
    if isinstance(regressors, list):
        for i, regressor in enumerate(regressors):
            if 'Name' not in regressor:
                regressor['Name'] = f'Regressor-{str(i + 1)}'
    if 'pipelineName' in orig_dict and len(original.strip()):
        middle_dict, leftovers_dict, complete_dict = update_config_dict(
            orig_dict)
        open(path, 'w').write(create_yaml_from_template(
            update_pipeline_values_1_8(middle_dict))
        )
        if leftovers_dict:
            open(f'{path}.rem', 'w').write(yaml.dump(leftovers_dict))
