import ckan.authz as authz
import ckan.plugins.toolkit as tk
import json
from ckan.common import config
from ckan.lib.base import render
import ckan.lib.mailer as mailer
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
        elif 'publication_date' in pkg_dict and pkg_dict['publication_date'] != '':
            #publication_date = datetime.strptime(pkg_dict['publication_date'], '%Y-%m-%d')
            publication_date = datetime.strptime(pkg_dict['publication_date'].split(' ', 1)[0], '%Y-%m-%d')
            #citation += ' (' + pkg_dict['publication_date'].year + '): '
            citation += ' (' + str(publication_date.year) + '): '
    citation += pkg_dict['title']

    if citation[len(citation) -1] != '.':
        citation += '.'
    citation += ' '

    if 'publisher' in pkg_dict:
        citation += pkg_dict['publisher'] + '. '
    if 'resource_type' in pkg_dict:
        citation += '(' + pkg_dict['resource_type'].capitalize() +'). '
    if 'doi' in pkg_dict:
        citation += 'https://doi.org/' + pkg_dict['doi']

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
                if 'owner_org' in package:
                    # There's only one org so we could probably get away with only doing this once
                    user_role = authz.users_role_for_group_or_org(package['owner_org'], user.name)
                    # Filter out any private datasets that the user did not create themselves if they are only a member
                    if user_role == 'member' and package['private'] and user.id != package['creator_user_id']:
                        filtered_results.remove(package)
                        result_count -= 1
            search_results['results'] = filtered_results
            search_results['count'] = result_count

    return search_results


def get_dataset_notification_body(context, pkg_dict):
    """
    Note: the proper way to do this would be with an email template, but
          CKAN couldn't find custom email templates as easily as it could
          HTML templates.
    """
    user = context.get('auth_user_obj')
    site_title = config.get('ckan.site_title')
    site_url = config.get('ckan.site_url')
    user_name = user.name
    user_email = 'Unknown'
    if user.email and user.email != '':
        user_email = user.email
    dataset_title = pkg_dict['title']
    dataset_url = config.get('ckan.site_url') + '/dataset/' + pkg_dict['name']
    return """
Dear AuScope Data Repository admin,

A dataset has been submitted by a user. The details are as follows:

Dataset title: {dataset_title}
User: {user_name}
User Email: {user_email}
Link to dataset: {dataset_url}

Please review this dataset or assign an editor to do so.

Thank you.

--
Message sent by {site_title} ({site_url})
    """.format(user_name=user_name, user_email=user_email, dataset_title=dataset_title, dataset_url=dataset_url, site_title=site_title, site_url=site_url)


def send_dataset_notification(context, pkg_dict):
    """
    Mail a dataset submission notification to the admin
    """
    body = get_dataset_notification_body(context, pkg_dict)
    site_title = config.get('ckan.site_title')
    dataset_title = pkg_dict['title']
    subject = 'AuScope Data Repository - Dataset Submitted "{dataset_title}"'.format(site_title=site_title, dataset_title=dataset_title)
    recipient_name = 'AuScope Data Repository admin'
    recipient_email = config.get('ckan_sysadmin_email')
    mailer.mail_recipient(recipient_name, recipient_email, subject, body)


@tk.chained_action
def after_dataset_update(context, pkg_dict):
    user = context.get('auth_user_obj')
    # Check package state is active (not a draft)
    if 'state' in pkg_dict and pkg_dict['state'] == 'active':
        if pkg_dict and 'owner_org' in pkg_dict:
            # Check that the user is a member (editors and admins won't be notified)
            user_role = authz.users_role_for_group_or_org(pkg_dict['owner_org'], user.name)
            if user_role == 'member' and 'private' in pkg_dict and pkg_dict['private'] == True:
                send_dataset_notification(context, pkg_dict)

