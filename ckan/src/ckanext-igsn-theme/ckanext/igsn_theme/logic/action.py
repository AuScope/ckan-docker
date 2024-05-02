from ckan import model
import ckan.plugins.toolkit as tk
import ckanext.igsn_theme.logic.schema as schema
import ckan.lib.plugins as lib_plugins
import ckan.logic as logic
from ckan.logic.validators import owner_org_validator as default_owner_org_validator
from ckan.logic.action.create import user_create as ckan_user_create
from ckan.logic import _actions
import ckan.authz as authz
import logging

@tk.side_effect_free
def igsn_theme_get_sum(context, data_dict):
    tk.check_access(
        "igsn_theme_get_sum", context, data_dict)
    data, errors = tk.navl_validate(
        data_dict, schema.igsn_theme_get_sum(), context)

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


# def group_list_auth(context, data_dict):
#     user = context['user']
#     user_obj = model.User.get(user)

#     if user_obj.sysadmin:
#         return {'success': True}  # Allow sysadmins to see all groups

#     user_groups = [group.id for group in user_obj.get_groups('group')]
#     if user_groups:
#         return {'success': True, 'output': user_groups}
#     else:
#         return {'success': False}


# def group_list(context, data_dict):
#     allowed_groups = group_list_auth(context, data_dict).get('output', [])
#     if allowed_groups:
#         return model.Session.query(model.Group).filter(model.Group.id.in_(allowed_groups)).all()
#     return []


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
    created_package = next_action(context, data_dict)
    return created_package


# We do not need user_create customization here.
# Users do not need to be a part of an organization by default.
# @tk.chained_action
# def user_create(next_action, context, data_dict):
#     user = ckan_user_create(context, data_dict)
#     # TODO: get from config
#     org_name = 'auscope'
#     role = 'member'
#     try:
#         tk.get_action('organization_show')(
#             context, {
#                 'id': org_name,
#             }
#         )
#     except logic.NotFound:
#         return user

#     tk.get_action('organization_member_create')(
#         context, {
#             'id': org_name,
#             'username': user['name'],
#             'role': role,
#         }
#     )
#     return user


def create_package_relationship(context, pkg_dict):
    if 'parent' in pkg_dict and pkg_dict['parent']:
        logger = logging.getLogger(__name__)
        parent_id = pkg_dict['parent']
        try:
            tk.get_action('package_relationship_create')(context, {
                'subject': pkg_dict['id'],
                'object': parent_id,
                'type': 'child_of',
                'comment': 'Creating a child_of relationship'
            })
        except Exception as e:
            logger.error('Failed to create package relationship: {}'.format(str(e)))


def update_package_relationship(context, pkg_dict):
    """
    Updates the parent relationship of a package.
    
    Parameters:
    context (dict): The context dictionary containing user and auth details.
    pkg_dict (dict): Dictionary containing the package details, including 'id' and optional 'parent'.
    
    Returns:
    None
    """
    if 'parent' in pkg_dict and pkg_dict['parent']:
        logger = logging.getLogger(__name__)
        parent_id = pkg_dict['parent']
        package_id = pkg_dict['id']
        relationship_type = 'child_of'
        try:
            existing_relationships = tk.get_action('package_relationships_list')(
                context, {'id': package_id, 'rel': relationship_type}
            )
            for rel in existing_relationships:
                tk.get_action('package_relationship_delete')(context, rel)
        except Exception as e:
                logger.error(f"Error while accessing relationships for package {package_id}: {str(e)}")
        try:
            tk.get_action('package_relationship_create')(context, {
                'subject': package_id,
                'object': parent_id,
                'type': relationship_type,
                'comment': 'Updated relationship to new parent'
            })
        except Exception as e:
            logger.error(f"Failed to create package relationship for package {package_id}: {str(e)}")


def delete_package_relationship(context, pkg_dict):
    logger = logging.getLogger(__name__)
    package_id = pkg_dict['id']
    try:
        existing_relationships = tk.get_action('package_relationships_list')(context, {'id': package_id})
        for rel in existing_relationships:
            tk.get_action('package_relationship_delete')(context, rel)
    except Exception as e:
        logger.error(f"Failed to delete package relationship: {str(e)}")

def get_actions():
    return {
        # 'user_create': user_create,
        'igsn_theme_get_sum': igsn_theme_get_sum,
        'organization_list_for_user': organization_list_for_user,
        'package_create': package_create,
        'create_package_relationship' : create_package_relationship,
        'update_package_relationship' : update_package_relationship,
        'delete_package_relationship' : delete_package_relationship
         # 'group_list': group_list,
    }
