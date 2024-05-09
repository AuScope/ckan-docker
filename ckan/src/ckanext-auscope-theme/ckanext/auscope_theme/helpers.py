from ckan.common import config
from ckan.plugins import toolkit
import ckan.logic as logic
import ckan.authz as authz
from datetime import date, datetime
from zoneinfo import ZoneInfo



def auscope_theme_hello():
    return "Hello, auscope_theme!"

def is_creating_or_editing_dataset():
    """Determine if the user is creating or editing a dataset."""
    current_path = toolkit.request.path
    if current_path.startswith('/dataset/new'):
        return True
    elif "/dataset/edit/" in current_path:
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

def current_date():
    return date.today().isoformat()

def render_tz_date_from_datetime(dt_str):
    # Convert from UTC if necessary
    if config.get('ckan.display_timezone'):
        if len(dt_str.split(' ', 1)) > 1:
            dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S.%f')
            dt = dt.astimezone(ZoneInfo(config.get('ckan.display_timezone')))
            dt_str = datetime.strftime(dt, '%Y-%m-%d')
    return dt_str


def get_helpers():
    return {
        "auscope_theme_hello": auscope_theme_hello,
        "is_creating_or_editing_dataset" :is_creating_or_editing_dataset,
        "get_search_facets" : get_search_facets,
        'get_org_list': get_org_list,
        'users_role_in_org': users_role_in_org,
        'current_date': current_date,
        'render_tz_date_from_datetime': render_tz_date_from_datetime,
    }
