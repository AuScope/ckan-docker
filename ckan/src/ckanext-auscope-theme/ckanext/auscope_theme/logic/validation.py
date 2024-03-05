import ckan.lib.navl.dictization_functions as df
import ckan.logic as logic
import ckan.authz as authz
import ckan.model as model
from ckantoolkit import ( _, missing )
from ckan.types import (
    FlattenDataDict, FlattenKey, Context, FlattenErrorDict)
from collections import OrderedDict
from logging import getLogger
from typing import Any, Optional


Invalid = df.Invalid
StopOnError = df.StopOnError
Missing = df.Missing
missing = df.missinglog = getLogger(__name__)


UPDATED_ROLE_PERMISSIONS: dict[str, list[str]] = OrderedDict([
    ('admin', ['admin', 'membership']),
    ('editor', ['read', 'delete_dataset', 'create_dataset',
                'update_dataset', 'manage_group']),
    ('member', ['read', 'delete_dataset', 'create_dataset',
                'update_dataset', 'manage_group']),
])

def has_user_permission_for_group_or_org(group_id: Optional[str],
                                         user_name: Optional[str],
                                         permission: str) -> bool:
    ''' Check if the user has the given permissions for the group, allowing for
    sysadmin rights and permission cascading down a group hierarchy.

    '''
    if not group_id:
        return False
    group = model.Group.get(group_id)
    if not group:
        return False
    group_id = group.id

    # Sys admins can do anything
    if authz.is_sysadmin(user_name):
        return True

    user_id = authz.get_user_id_for_username(user_name, allow_none=True)
    if not user_id:
        return False
    if _has_user_permission_for_groups(user_id, permission, [group_id]):
        return True
    capacities = check_config_permission('roles_that_cascade_to_sub_groups')
    assert isinstance(capacities, list)
    # Handle when permissions cascade. Check the user's roles on groups higher
    # in the group hierarchy for permission.
    for capacity in capacities:
        parent_groups = group.get_parent_group_hierarchy(type=group.type)
        group_ids = [group_.id for group_ in parent_groups]
        if _has_user_permission_for_groups(user_id, permission, group_ids,
                                           capacity=capacity):
            return True
    return False


def _has_user_permission_for_groups(
        user_id: str, permission: str, group_ids: list[str],
        capacity: Optional[str]=None) -> bool:
    ''' Check if the user has the given permissions for the particular
    group (ignoring permissions cascading in a group hierarchy).
    Can also be filtered by a particular capacity.
    '''
    if not group_ids:
        return False
    # get any roles the user has for the group
    q: Any = (model.Session.query(model.Member.capacity)
         # type_ignore_reason: attribute has no method
         .filter(model.Member.group_id.in_(group_ids))
         .filter(model.Member.table_name == 'user')
         .filter(model.Member.state == 'active')
         .filter(model.Member.table_id == user_id))

    if capacity:
        q = q.filter(model.Member.capacity == capacity)
    # see if any role has the required permission
    # admin permission allows anything for the group
    for row in q:
        perms = UPDATED_ROLE_PERMISSIONS.get(row.capacity, [])
        if 'admin' in perms or permission in perms:
            return True
    return False


# A dictionary to store your validators
all_validators = {}

def register_validator(fn):
    """
    collect validator functions into ckanext.scheming.all_helpers dict
    """
    all_validators[fn.__name__] = fn
    return fn


def scheming_validator(fn):
    """
    Decorate a validator that needs to have the scheming fields
    passed with this function. When generating navl validator lists
    the function decorated will be called passing the field
    and complete schema to produce the actual validator for each field.
    """
    fn.is_a_scheming_validator = True
    return fn


@scheming_validator
@register_validator
def visibility_validator(field, schema):
    def validator(key: FlattenKey, data: FlattenDataDict,
                  errors: FlattenErrorDict, context: Context) -> Any:
        """
        Validate that the user has sufficient privilege (admin or editor) to make a dataset public
        """
        value = data.get(key)

        if value is missing or value is None:
            if not authz.check_config_permission('create_unowned_dataset'):
                raise Invalid(_('An organization must be provided'))
            data.pop(key, None)
            raise df.StopOnError

        model = context['model']
        user = model.User.get(context['user'])
        package = context.get('package')

        if value == '':
            if not authz.check_config_permission('create_unowned_dataset'):
                raise Invalid(_('An organization must be provided'))
            return

        if (authz.check_config_permission('allow_dataset_collaborators')
                and not authz.check_config_permission('allow_collaborators_to_change_owner_org')):

            if package and user and not user.sysadmin:
                is_collaborator = authz.user_is_collaborator_on_dataset(
                    user.id, package.id, ['admin', 'editor'])
                if is_collaborator:
                    # User is a collaborator, check if it's also a member with
                    # edit rights of the current organization (redundant, but possible)
                    user_orgs = logic.get_action(
                        'organization_list_for_user')(
                            {'ignore_auth': True}, {'id': user.id, 'permission': 'update_dataset'})
                    user_is_org_member = package.owner_org in [org['id'] for org in user_orgs]
                    if data.get(key) != package.owner_org and not user_is_org_member:
                        raise Invalid(_('You cannot move this dataset to another organization'))

        group = model.Group.get(value)
        if not group:
            raise Invalid(_('Organization does not exist'))
        group_id = group.id

        if not package or (package and package.owner_org != group_id):
            # This is a new dataset or we are changing the organization
            if not context.get(u'ignore_auth', False) and (not user or not(
                    user.sysadmin or has_user_permission_for_group_or_org(
                        group_id, user.name, 'create_dataset'))):
                raise Invalid(_('You cannot add a dataset to this organization'))
        user_role = authz.users_role_for_group_or_org('auscope', user.name)
        if not (user_role == 'editor' or user_role == 'admin') and (package and package.private == False):
            raise Invalid(_('Only editors can make a dataset public after it has been reviewed'))

        data[key] = group_id
    return validator


@scheming_validator
@register_validator
def location_validator(field, schema):
    def validator(key, data, errors, context):
        location_choice_key = ('location_choice',)
        point_latitude_key = ('point_latitude',)
        point_longitude_key = ('point_longitude',)
        bounding_box_key = ('bounding_box',)

        location_choice = data.get(location_choice_key, missing)
        point_latitude = data.get(point_latitude_key, missing)
        point_longitude = data.get(point_longitude_key, missing)
        bounding_box = data.get(bounding_box_key, missing)

        missing_error = _("Missing value")
        invalid_error = _("Invalid value")

        def add_error(key, error_message):
            errors[key] = errors.get(key, [])
            errors[key].append(error_message)

        # Exit the validation for noLocation choice
        if location_choice == 'noLocation':
            for key in [point_latitude_key, point_longitude_key, bounding_box_key]:
                data[key] = None
            return

        if location_choice == 'point':
            # Validate latitude
            if point_latitude is missing:
                add_error(point_latitude_key, missing_error)
            elif not is_valid_latitude(point_latitude):
                add_error(point_latitude_key, invalid_error)

            # Validate longitude
            if point_longitude is missing:
                add_error(point_longitude_key, missing_error)
            elif not is_valid_longitude(point_longitude):
                add_error(point_longitude_key, invalid_error)

        elif location_choice == 'area':
            # Validate bounding box
            if bounding_box is missing:
                add_error(bounding_box_key, missing_error)
            elif not is_valid_bounding_box(bounding_box):
                add_error(bounding_box_key, invalid_error)

        # Handle missing location choice
        if location_choice is missing and field.get('required', False):
            add_error(location_choice_key, missing_error)

    return validator

def is_valid_latitude(lat):
    try:
        lat = float(lat)
        return -90 <= lat <= 90
    except (ValueError, TypeError):
        return False

def is_valid_longitude(lng):
    try:
        lng = float(lng)
        return -180 <= lng <= 180
    except (ValueError, TypeError):
        return False
    
def is_valid_bounding_box(bbox):
    try:
        # If bbox is a list with one element, extract the string
        if isinstance(bbox, list) and len(bbox) == 1:
            bbox = bbox[0]

        # Check if bbox is a string in the correct format
        if not isinstance(bbox, str) or len(bbox.split(',')) != 4:
            return False

        # Split the string and convert each part to float
        min_lng , min_lat, max_lng , max_lat = map(float, bbox.split(','))

        return all(-90 <= lat <= 90 for lat in [min_lat, max_lat]) and \
               all(-180 <= lng <= 180 for lng in [min_lng, max_lng]) and \
               min_lat < max_lat and min_lng < max_lng
    except (ValueError, TypeError):
        return False

