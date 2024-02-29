import ckan.plugins.toolkit as tk
import ckan.authz as authz
from ckan.logic.auth import get_package_object, get_resource_object
from ckan.logic.auth.create import package_create as ckan_package_create
from ckan.logic.auth.update import package_update as ckan_package_update


@tk.auth_allow_anonymous_access
def auscope_theme_get_sum(context, data_dict):
    return {"success": True}


def user_is_member_of_package_org(user, package):
    """
    Return True if the package is in an organization and the user has the member role in
    that organization.

    :param user: A user object
    :param package: A package object
    :returns: True if the user has the 'member' role in the organization that owns the
              package, False otherwise
    """
    if package.owner_org:
        role_in_org = authz.users_role_for_group_or_org(package.owner_org, user.name)
        if role_in_org == 'member':
            return True
    return False


def user_owns_package_as_member(user, package):
    """
    Checks that the given user created the package, and has the 'member' role in the
    organization that owns the package.

    :param user: A user object
    :param package: A package object
    :returns: True if the user created the package and has the 'member' role in the
              organization to which package belongs. False otherwise.
    """
    if user_is_member_of_package_org(user, package):
        return package.creator_user_id and user.id == package.creator_user_id

    return False


@tk.chained_auth_function
def package_create(next_auth, context, data_dict):
    user = context.get('auth_user_obj')

    if data_dict and 'owner_org' in data_dict:
        user_role = authz.users_role_for_group_or_org(data_dict['owner_org'], user.name)
        # userdatasets only checks for 'member' here
        if user_role in ['admin', 'editor', 'member']:
            return {'success': True}
    else:
        if authz.has_user_permission_for_some_org(user.name, 'read'):
            return {'success': True}
    return next_auth(context, data_dict)


@tk.chained_auth_function
def resource_create(next_auth, context, data_dict):
    user = context['auth_user_obj']
    package = get_package_object(context, {'id': data_dict['package_id']})
    if user_owns_package_as_member(user, package):
        return {'success': True}
    elif user_is_member_of_package_org(user, package):
        return {'success': False}
    return next_auth(context, data_dict)


@tk.chained_auth_function
def resource_view_create(next_auth, context, data_dict):
    user = context['auth_user_obj']
    # data_dict provides 'resource_id', while get_resource_object expects 'id'. This is
    # not consistent with the rest of the API - so future proof it by catering for both
    # cases in case the API is made consistent (one way or the other) later.
    if data_dict and 'resource_id' in data_dict:
        dc = {'id': data_dict['resource_id'], 'resource_id': data_dict['resource_id']}
    elif data_dict and 'id' in data_dict:
        dc = {'id': data_dict['id'], 'resource_id': data_dict['id']}
    else:
        dc = data_dict
    resource = get_resource_object(context, dc)
    if user_owns_package_as_member(user, resource.package):
        return {'success': True}
    elif user_is_member_of_package_org(user, resource.package):
        return {'success': False}

    return next_auth(context, data_dict)


@tk.chained_auth_function
def package_update(next_auth, context, data_dict):
    user = context.get('auth_user_obj')

    try:
        package = get_package_object(context, data_dict)
    except:
        return {'success': False, 'msg': 'Unable to retrieve package'}

    if package.owner_org:
        user_role = authz.users_role_for_group_or_org(package.owner_org, user.name)
        if user_role in ['editor', 'admin']:
            return {'success': True}
        elif user_role == 'member' and package.creator_user_id and package.creator_user_id == user.id:
            return {'success': True}

    return next_auth(context, data_dict)


@tk.chained_auth_function
def resource_update(next_auth, context, data_dict):
    '''
    :param next_auth:
    :param context:
    :param data_dict:

    '''
    user = context['auth_user_obj']
    resource = get_resource_object(context, data_dict)
    package = resource.packageA


    if package.owner_org:
        user_role = authz.users_role_for_group_or_org(package.owner_org, user.name)
        if user_role in ['editor', 'admin']:
            return {'success': True}
        elif user_role == 'member' and package.creator_user_id and package.creator_user_id == user.id:
            return {'success': True}
    """
    if user_owns_package_as_member(user, package):
        return {'success': True}
    elif user_is_member_of_package_org(user, package):
        return {'success': False}
    """

    return next_auth(context, data_dict)


@tk.chained_auth_function
def resource_view_update(next_auth, context, data_dict):
    '''
    :param next_auth:
    :param context:
    :param data_dict:

    '''
    user = context['auth_user_obj']
    resource_view = get_resource_view_object(context, data_dict)
    resource = get_resource_object(context, {'id': resource_view.resource_id})


    if package.owner_org:
        user_role = authz.users_role_for_group_or_org(package.owner_org, user.name)
        if user_role in ['editor', 'admin']:
            return {'success': True}
        elif user_role == 'member' and package.creator_user_id and package.creator_user_id == user.id:
            return {'success': True}
    """
    if user_owns_package_as_member(user, resource.package):
        return {'success': True}
    elif user_is_member_of_package_org(user, resource.package):
        return {'success': False}
    """

    return next_auth(context, data_dict)


@tk.chained_auth_function
def package_delete(next_auth, context, data_dict):
    user = context.get('user')
    user_id = authz.get_user_id_for_username(user)
    try:
        package = get_package_object(context, data_dict)
    except:
        return {'success': False, 'msg': 'Unable to retrieve package'}
    user_role = authz.users_role_for_group_or_org(package.owner_org, user)
    if user_role == 'admin' or user_role == 'editor':
        return {'success': True}
    if user_role == 'member' and package.creator_user_id and user_id == package.creator_user_id:
        return {'success': True}
    else:
        return {'success': False, 'msg': 'Unauthorized to delete dataset.'}

    return next_auth(context, data_dict)


@tk.chained_auth_function
def resource_delete(next_auth, context, data_dict):
    user = context['auth_user_obj']
    resource = get_resource_object(context, data_dict)
    package = resource.package

    user_role = authz.users_role_for_group_or_org(package.owner_org, user)
    if user_role == 'admin' or user_role == 'editor':
        return {'success': True}
    if user_role == 'member' and package.creator_user_id and user_id == package.creator_user_id:
        return {'success': True}
    else:
        return {'success': False, 'msg': 'Unauthorized to delete dataset.'}
    """
    if user_owns_package_as_member(user, package):
        return {'success': True}
    elif user_is_member_of_package_org(user, package):
        return {'success': False}
    """

    return next_auth(context, data_dict)


@tk.chained_auth_function
def resource_view_delete(next_auth, context, data_dict):
    user = context['auth_user_obj']
    resource_view = get_resource_view_object(context, data_dict)
    resource = get_resource_object(context, {'id': resource_view.resource_id})

    user_role = authz.users_role_for_group_or_org(package.owner_org, user)
    if user_role == 'admin' or user_role == 'editor':
        return {'success': True}
    if user_role == 'member' and package.creator_user_id and user_id == package.creator_user_id:
        return {'success': True}
    else:
        return {'success': False, 'msg': 'Unauthorized to delete dataset.'}
    """
    if user_owns_package_as_member(user, resource.package):
        return {'success': True}
    elif user_is_member_of_package_org(user, resource.package):
        return {'success': False}
    """

    return next_auth(context, data_dict)


def get_auth_functions():
    return {
        "auscope_theme_get_sum": auscope_theme_get_sum,
        "package_create": package_create,
        "package_update": package_update,
        "package_delete": package_delete,
        "resource_create": resource_create,
        "resource_view_create": resource_view_create,
    }

