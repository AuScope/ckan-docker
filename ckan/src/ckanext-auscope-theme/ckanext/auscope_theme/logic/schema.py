import ckan.authz as authz
import ckan.plugins.toolkit as tk
import json
from datetime import datetime



def auscope_theme_get_sum():
    not_empty = tk.get_validator("not_empty")
    convert_int = tk.get_validator("convert_int")

    return {
        "left": [not_empty, convert_int],
        "right": [not_empty, convert_int]
    }


@tk.chained_action
def after_dataset_show(context, pkg_dict):
    """
    Add the Citation details to the pkg_dict so it can be displayed
    Format:
        Authors (PublicationYear): Title. Publisher. (ResourceType). Identifier
    Example:
        Irino, T; Tada, R (2009): Chemical and mineral compositions of sediments from ODP Site 127-797. V. 2.1. Geological Institute, University of Tokyo. (dataset). https://doi.org/10.1594/PANGAEA.726855
    """
    citation = ''
    author_list = json.loads(pkg_dict['author'])
    for i in range(0, len(author_list)):
        citation += author_list[i]['author_name']
        if i != len(author_list) - 1:
            citation += ', '
        # TODO: Change this to publication_date when dataset is published (and when field is reinstated)
        elif 'deposit_date' in pkg_dict:
            deposit_date = datetime.strptime(pkg_dict['deposit_date'], '%Y-%m-%d')
            citation += ' (' + str(deposit_date.year) + '): '
    citation += pkg_dict['title']

    if citation[len(citation) -1] != '.':
        citation += '.'
    citation += ' '

    if 'publisher' in pkg_dict:
        citation += pkg_dict['publisher'] + '. '
    if 'resource_type' in pkg_dict:
        citation += '(' + pkg_dict['resource_type'].capitalize() +'). '
    if 'doi' in pkg_dict:
        citation += pkg_dict['doi']

    pkg_dict['citation'] = citation


@tk.chained_action
def after_dataset_search(search_results, search_params):
    """
    Filtered returned search results so that members do not see other user's private datasets.
    Editors and admins will still see all datasets.
    """
    result_count = search_results['count']
    if result_count > 0:
        user = tk.g.userobj
        if user:
            filtered_results = search_results['results'].copy()
            for package in search_results['results']:
                # There's only one org so we could probably get away with only doing this once
                user_role = authz.users_role_for_group_or_org(package['owner_org'], user.name)
                # Filter out any private datasets that the user did not create themselves if they are only a member
                # and aren't a dataset collaborator
                if user_role == 'member' and package['private'] and user.id != package['creator_user_id'] \
                        and not authz.user_is_collaborator_on_dataset(user.id, package['id']):
                    filtered_results.remove(package)
                    result_count -= 1
            search_results['results'] = filtered_results
            search_results['count'] = result_count

    return search_results

