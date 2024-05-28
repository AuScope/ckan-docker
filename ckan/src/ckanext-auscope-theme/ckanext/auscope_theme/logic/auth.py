import ckan.plugins.toolkit as tk
import ckan.authz as authz
from ckan.logic.auth import get_package_object, get_resource_object
from ckan.logic.auth.create import package_create as ckan_package_create
from ckan.logic.auth.update import package_update as ckan_package_update


@tk.auth_allow_anonymous_access
def auscope_theme_get_sum(context, data_dict):
    return {"success": True}


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

    if package.owner_org:
        user_role = authz.users_role_for_group_or_org(package.owner_org, user.name)
        # Admins can always edit a resource
        if user_role == 'admin':
            return {'success': True}
        # Can't edit a published resource unless admin
        elif not package.private:
            return {'success': False, 'msg': 'You are not authorised to add a resource to a published dataset'}
        # Members and editors can only update their own resources IF the dataset has not been published (private)
        elif (user_role == 'member' or user_role == 'editor') and package.creator_user_id and package.creator_user_id == user.id:
            return {'success': True}

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

    if resource and resource.package and resource.package.owner_org:
        package = resource.package
        user_role = authz.users_role_for_group_or_org(package.owner_org, user.name)
        # Editors and admins can always view a resoure
        if user_role in ['editor', 'admin']:
            return {'success': True}
        # Members can view their own resources
        elif user_role == 'member' and package.creator_user_id and package.creator_user_id == user.id:
            return {'success': True}
        # Member is an editing collaborator
        elif hasattr(user, 'id') and authz.user_is_collaborator_on_dataset(user.id, package.id, ['editor']):
            return {'success': True}
        else:
            return {'success': False, 'msg': 'Unauthorized to view dataset'}

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
        # Editors and admins can always edit a package (editors require to package_update to publish)
        if user_role in ['editor', 'admin']:
            return {'success': True}
        # Members can edit package if it hasn't been published (is private)
        elif user_role == 'member' and package.creator_user_id and package.creator_user_id == user.id and package.private:
            return {'success': True}
        # Member is an editing collaborator and package has not been published
        elif hasattr(user, 'id') and authz.user_is_collaborator_on_dataset(user.id, package.id, ['editor']) and package.private:
            return {'success': True}
        else:
            return {'success': False, 'msg': 'Unauthorized to update dataset'}

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
    package = resource.package

    if package.owner_org:
        user_role = authz.users_role_for_group_or_org(package.owner_org, user.name)
        # Admins and editors can always edit a resource
        if user_role == 'admin':
            return {'success': True}
        # Can't edit a published resource unless admin/editor
        elif not package.private:
            return {'success': False, 'msg': 'You are not authorised to edit a resource of a published dataset'}
        # Members and editors can only update their own resources IF the dataset has not been published (private)
        elif (user_role == 'member' or user_role=='editor') and package.creator_user_id and package.creator_user_id == user.id:
            return {'success': True}
        # Member is an editing collaborator and package has not been published
        elif hasattr(user, 'id') and authz.user_is_collaborator_on_dataset(user.id, package.id, ['editor']):
            return {'success': True}

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
    package = resource.package

    if package.owner_org:
        user_role = authz.users_role_for_group_or_org(package.owner_org, user.name)
        # Admins can always edit a resource
        if user_role == 'admin':
            return {'success': True}
        # Can't edit a published resource unless admin
        elif not package.private:
            return {'success': False, 'msg': 'You are not authorised to edit a resource view of a published dataset'}
        # Members and editors can only update their own resources IF the dataset has not been published (private)
        elif (user_role == 'member' or user_role == 'editor') and package.creator_user_id and package.creator_user_id == user.id:
            return {'success': True}

    return next_auth(context, data_dict)


@tk.chained_auth_function
def package_delete(next_auth, context, data_dict):
    user = context['auth_user_obj']
    try:
        package = get_package_object(context, data_dict)
    except:
        return {'success': False, 'msg': 'Unable to retrieve package'}
    user_role = authz.users_role_for_group_or_org(package.owner_org, user.name)
    if user_role == 'admin':
        return {'success': True}
    elif not package.private:
        return {'success': False, 'msg': 'You are not authorised to delete a published dataset'}
    elif (user_role == 'member' or user_role == 'editor') and package.creator_user_id and user.id == package.creator_user_id:
        return {'success': True}
    else:
        return {'success': False, 'msg': 'Unauthorized to delete dataset'}

    return next_auth(context, data_dict)


@tk.chained_auth_function
def resource_delete(next_auth, context, data_dict):
    user = context['auth_user_obj']
    resource = get_resource_object(context, data_dict)
    package = resource.package

    user_role = authz.users_role_for_group_or_org(package.owner_org, user.name)
    if user_role == 'admin':
        return {'success': True}
    elif not package.private:
            return {'success': False, 'msg': 'You are not authorised to delete a published resource'}
    elif (user_role == 'member' or user_role == 'editor') and package.creator_user_id and user.id == package.creator_user_id:
        return {'success': True}
    else:
        return {'success': False, 'msg': 'Unauthorized to delete resource'}

    return next_auth(context, data_dict)


@tk.chained_auth_function
def resource_view_delete(next_auth, context, data_dict):
    user = context['auth_user_obj']
    resource_view = get_resource_view_object(context, data_dict)
    resource = get_resource_object(context, {'id': resource_view.resource_id})
    package = resource.package

    user_role = authz.users_role_for_group_or_org(package.owner_org, user.name)
    if user_role == 'admin':
        return {'success': True}
    elif not package.private:
            return {'success': False, 'msg': 'You are not authorised to delete a published resource view'}
    elif (user_role == 'member' or user_role == 'editor') and package.creator_user_id and user.id == package.creator_user_id:
        return {'success': True}
    else:
        return {'success': False, 'msg': 'Unauthorized to delete resource view'}

    return next_auth(context, data_dict)


@tk.chained_auth_function
def package_show(next_auth, context, data_dict):
    user = context.get('auth_user_obj')
    package = get_package_object(context, data_dict)

    if package and package.owner_org:
        user_role = authz.users_role_for_group_or_org(package.owner_org, user.name)
        if (user_role != 'admin' and user_role != 'editor') and package.private and hasattr(user, 'id') and package.creator_user_id != user.id \
                and not authz.user_is_collaborator_on_dataset(user.id, package.id):
            return {'success': False, 'msg': 'This dataset is private.'}

    return next_auth(context, data_dict)


@tk.chained_auth_function
def package_list(next_auth, context, data_dict):
    """
    Let any user bring up a package list
    """
    return {'success': True}


def get_auth_functions():
    return {
        "auscope_theme_get_sum": auscope_theme_get_sum,
        "package_create": package_create,
        "resource_create": resource_create,
        "resource_view_create": resource_view_create,
        "package_update": package_update,
        "resource_update": resource_update,
        "resource_view_update": resource_view_update,
        "package_delete": package_delete,
        "resource_delete": resource_delete,
        "resource_view_delete": resource_view_delete,
        "package_show": package_show,
        "package_list": package_list,
    }

