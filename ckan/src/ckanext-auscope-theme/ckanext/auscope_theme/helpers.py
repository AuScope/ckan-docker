from ckan.plugins import toolkit
import ckan.logic as logic
import ckan.authz as authz



def auscope_theme_hello():
    return "Hello, auscope_theme!"


def is_creating_dataset():
    """Determine if the user is creating or managing a dataset."""
    current_path = toolkit.request.path
    if current_path.startswith('/dataset/new'):
        return True
    return False


def get_search_facets():
    context = {'user': toolkit.c.user or toolkit.c.author}
    data_dict = {
        'q': '*:*',
        'facet.field': toolkit.h.facets(),
        'rows': 4,
        'start': 0,
        'sort': 'view_recent desc',
        'fq': 'capacity:"public"'
    }
    try:
        query = logic.get_action('package_search')(context, data_dict)
        return query['search_facets']
    except toolkit.ObjectNotFound:
        return {}


def get_org_list():
    return toolkit.get_action('organization_list_for_user')()


def users_role_in_org(user_name):
    # TODO: Get org name from config and pass in
    return authz.users_role_for_group_or_org(group_id='auscope', user_name=user_name)


def get_helpers():
    return {
    }


def get_helpers():
    return {
        "auscope_theme_hello": auscope_theme_hello,
        "is_creating_dataset" :is_creating_dataset,
        "get_search_facets" : get_search_facets,
        'get_org_list': get_org_list,
        'users_role_in_org': users_role_in_org,
    }
