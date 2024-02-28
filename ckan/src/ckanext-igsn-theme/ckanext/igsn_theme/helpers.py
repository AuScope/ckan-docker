from ckan.plugins import toolkit
import ckan.logic as logic

def igsn_theme_hello():
    return "Hello, igsn_theme!"

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


def get_helpers():
    return {
        "igsn_theme_hello": igsn_theme_hello,
        "is_creating_dataset" :is_creating_dataset,
        "get_search_facets" : get_search_facets
    }
