import ckan.plugins.toolkit as tk
import ckanext.auscope_theme.logic.schema as schema
import ckan.lib.plugins as lib_plugins
import ckan.logic as logic
from ckan.logic.validators import owner_org_validator as default_owner_org_validator
from ckanext.auscope_theme.logic.validators import owner_org_validator
from ckan.logic.action.create import user_create as ckan_user_create
from datetime import datetime
from ckan.logic.auth import get_package_object



@tk.side_effect_free
def auscope_theme_get_sum(context, data_dict):
    tk.check_access(
        "auscope_theme_get_sum", context, data_dict)
    data, errors = tk.navl_validate(
        data_dict, schema.auscope_theme_get_sum(), context)

    if errors:
        raise tk.ValidationError(errors)

    return {
        "left": data["left"],
        "right": data["right"],
        "sum": data["left"] + data["right"]
    }


@tk.chained_action
def organization_list_for_user(next_action, context, data_dict):
    # Allow all users to see organization list
    perm = data_dict.get('permission')
    if perm in ['create_dataset', 'update_dataset', 'delete_dataset']:
        data_dict = {**data_dict, **{'permission': 'read'}}
    return next_action(context, data_dict)


@tk.chained_action
def package_create(next_action, context, data_dict):
    package_type = data_dict.get('type')
    package_plugin = lib_plugins.lookup_package_plugin(package_type)
    if 'schema' in context:
        schema = context['schema']
    else:
        schema = package_plugin.create_package_schema()
    # Replace owner_org_validator
    if 'owner_org' in schema:
        schema['owner_org'] = [
            owner_org_validator if f is default_owner_org_validator else f
            for f in schema['owner_org']
        ]
    context['schema'] = schema

    # Set deposit date
    data_dict['deposit_date'] = datetime.now()

    # Editors/admins may create dataset as public, so add publication date
    if data_dict['private'] == 'False':
        data_dict['publication_date'] = datetime.now()

    return next_action(context, data_dict)


@tk.chained_action
def package_update(next_action, context, data_dict):
    package = get_package_object(context, {'id': data_dict['id']})
    # If package being made public for first time, set publication date
    if package.private and data_dict['private'] == 'False' and \
            (not data_dict['publication_date'] or data_dict['publication_date'] == ''):
        data_dict['publication_date'] = datetime.now()
    return next_action(context, data_dict)


@tk.chained_action
def package_search(next_action, context, data_dict):
    """
    Overwrite package_search so that it will ignore auth so all results are returned
    """
    context['ignore_auth'] = True
    return next_action(context, data_dict)


@tk.chained_action
def user_create(next_action, context, data_dict):
    user = ckan_user_create(context, data_dict)
    # TODO: get from config
    org_name = 'auscope'
    role = 'member'
    try:
        tk.get_action('organization_show')(
            context, {
                'id': org_name,
            }
        )
    except logic.NotFound:
        return user

    tk.get_action('organization_member_create')(
        context, {
            'id': org_name,
            'username': user['name'],
            'role': role,
        }
    )
    return user


def get_actions():
    return {
        'user_create': user_create,
        'auscope_theme_get_sum': auscope_theme_get_sum,
        'organization_list_for_user': organization_list_for_user,
        'package_create': package_create,
        'package_update': package_update,
        'package_search': package_search,
    }
