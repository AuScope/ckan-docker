import ckan.lib.navl.dictization_functions as df
import ckan.logic as logic
import ckan.authz as authz
import ckan.model as model
from ckantoolkit import ( _, missing , get_validator )
from ckan.types import (
    FlattenDataDict, FlattenKey, Context, FlattenErrorDict)
from collections import OrderedDict
from datetime import datetime
from logging import getLogger
from typing import Any, Optional

import ckan.plugins.toolkit as tk
import ckanext.scheming.helpers as sh
from ckanext.scheming.validation import scheming_validator, register_validator
import json



Invalid = df.Invalid
StopOnError = df.StopOnError
Missing = df.Missing
missing = df.missinglog = getLogger(__name__)

StopOnError = df.StopOnError
not_empty = get_validator('not_empty')

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

        # Check user is editor or admin if they're tryin to make a dataset public (publish)
        is_private = data.get(('private',))
        user_role = authz.users_role_for_group_or_org('auscope', user.name)
        #if not (user_role == 'editor' or user_role == 'admin') and (package and package.private == False):
        if not (user_role == 'editor' or user_role == 'admin') and is_private == 'False':
            raise Invalid(_('Only editors can make a dataset public after it has been reviewed'))

        # Check embargo period has ended if making public (publish)
        embargo_date_str = data.get(('embargo_date',))
        if embargo_date_str is not None and embargo_date_str != '' and is_private == 'False':
            today = datetime.today()
            date_format = '%Y-%m-%d'
            embargo_date = datetime.strptime(embargo_date_str, date_format)
            if today < embargo_date:
                raise Invalid(_('This dataset cannot be made public until the embargo date (' + embargo_date.strftime(date_format)  + ').'))

        data[key] = group_id
    return validator


@scheming_validator
@register_validator
def location_validator(field, schema):
    def validator(key, data, errors, context):
        missing_error = _("Missing value")
        invalid_error = _("Invalid value")

        location_choice_key = ('location_choice',)
        location_data_key = ('location_data',)
        elevation_key = ('elevation',)
        vertical_datum_key = ('vertical_datum',)
        epsg_code_key = ('epsg_code',)

        location_choice = data.get(location_choice_key, missing)
        location_data = data.get(location_data_key, missing)
        elevation = data.get(elevation_key, missing)
        vertical_datum = data.get(vertical_datum_key, missing)
        epsg_code = data.get(epsg_code_key, missing)

        def add_error(key, error_message):
            errors[key] = errors.get(key, [])
            errors[key].append(error_message)

        # Exit the validation for noLocation choice
        if location_choice == 'noLocation':
            for key in [location_data_key]:
                data[key] = None
            return
        
        # Check if location_data needs parsing or is already a dict
        if isinstance(location_data, str):
            try:
                location_data = json.loads(location_data)
            except ValueError:
                add_error(location_data_key, invalid_error)
                return
        elif not isinstance(location_data, dict):
            add_error(location_data_key, invalid_error)
            return
                
          
        features = location_data.get('features', [])
        if not features:
            add_error(location_data_key, missing_error)
            return

        if location_choice == 'point':
            for feature in features:
                if feature['geometry']['type'] == 'Point':
                    coords = feature['geometry']['coordinates']
                    if not is_valid_longitude(coords[0]) or not is_valid_latitude(coords[1]):
                        add_error(location_data_key, invalid_error)
                        break

        elif location_choice == 'area':
            for feature in features:
                if feature['geometry']['type'] == 'Polygon':
                    for polygon in feature['geometry']['coordinates']:
                        for coords in polygon:
                            if not is_valid_longitude(coords[0]) or not is_valid_latitude(coords[1]):
                                add_error(location_data_key, invalid_error)
                                return

        else:
            add_error(location_data_key, missing_error)

        if location_choice is missing and field.get('required', False):
            add_error(location_choice_key, missing_error)
        
        if epsg_code is missing:
            add_error(epsg_code_key, missing_error)

        if elevation and elevation is not missing:
            if vertical_datum is missing:
                add_error(vertical_datum_key, missing_error)
                
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
    
def composite_not_empty_subfield(key, subfield_label, value, errors):
    '''
    Validates that a specified subfield is not empty. If the subfield is empty,
    appends a custom error message that includes the subfield label.
    
    Parameters:
        key (tuple): The key in the data dictionary that corresponds to the main field.
        subfield_label (str): The label of the subfield to be included in the error message.
        value (str): The value of the subfield to validate.
        errors (dict): A dictionary where validation errors are collected.
    '''
    if not value or value is missing:
        if key not in errors:
            errors[key] = []
        
        if errors[key] and "Missing value at required subfields:" in errors[key][-1]:
            errors[key][-1] += f", {subfield_label}"
        else:
            errors[key].append(f"Missing value at required subfields: {subfield_label}")



def composite_all_empty(field, item):
    all_empty = True
    for schema_subfield in field['subfields']:
        subfield_value = item.get(schema_subfield.get('field_name', ''), "")
        if subfield_value and subfield_value is not missing:
            all_empty = False
    return all_empty

def author_validator(key, item, index, field, errors):
    author_identifier_key = f'author_identifier'
    author_identifier_type_key = f'author_identifier_type'

    author_identifier = item.get(author_identifier_key, "")
    author_identifier_type = item.get(author_identifier_type_key, "")
    
    if author_identifier and author_identifier is not missing:
        for subfield in field['subfields']:
            if subfield.get('field_name') == 'author_identifier_type':
                author_identifier_type_label = subfield.get('label', 'Default Label') + " " + str(index)
                break  
        composite_not_empty_subfield(key,  author_identifier_type_label , author_identifier_type, errors)

def funder_validator(key, item, index, field, errors):
    funder_identifier_key = f'funder_identifier'
    funder_identifier_type_key = f'funder_identifier_type'

    funder_identifier = item.get(funder_identifier_key, "")
    funder_identifier_type = item.get(funder_identifier_type_key, "")
    
    if funder_identifier and funder_identifier is not missing:
        for subfield in field['subfields']:
            if subfield.get('field_name') == 'funder_identifier_type':
                funder_identifier_type_label = subfield.get('label', 'Default Label') + " " + str(index)
                break  
        composite_not_empty_subfield(key,  funder_identifier_type_label , funder_identifier_type, errors)

def project_validator(key, item, index, field, errors):
    project_name_key = f'project_name'
    project_identifier_key = f'project_identifier'
    project_identifier_type_key = f'project_identifier_type'

    project_name = item.get(project_name_key, "")
    project_identifier = item.get(project_identifier_key, "")
    project_identifier_type = item.get(project_identifier_type_key, "")
    
    if project_name and project_name is not missing:
        for subfield in field['subfields']:
            if subfield.get('field_name') == 'project_identifier':
                project_identifier_label = subfield.get('label', 'Default Label') + " " + str(index)
            if subfield.get('field_name') == 'project_identifier_type':
                project_identifier_type_label = subfield.get('label', 'Default Label') + " " + str(index)                

        composite_not_empty_subfield(key,  project_identifier_label , project_identifier, errors)           
        composite_not_empty_subfield(key,  project_identifier_type_label , project_identifier_type, errors)

@scheming_validator
@register_validator
def composite_repeating_validator(field, schema):
    def validator(key, data, errors, context):
        value = ""

        for name, text in data.items():
            if name == key:
                if text:
                    value = text

        # parse from extra into a list of dictionaries and save it as a json dump
        if not value:
            found = {}
            prefix = key[-1] + '-'
            extras = data.get(key[:-1] + ('__extras',), {})

            extras_to_delete = []
            for name, text in extras.items():
                if not name.startswith(prefix):
                    continue

                # if not text:
                #    continue

                index = int(name.split('-', 2)[1])
                subfield = name.split('-', 2)[2]
                extras_to_delete += [name]

                if index not in found.keys():
                    found[index] = {}
                found[index][subfield] = text
            found_list = [element[1] for element in sorted(found.items())]

            if not found_list:
                data[key] = ""
            else:

                # check if there are required subfields missing for every item
                for index in found:
                    item = found[index]

                    item_is_empty_and_optional = composite_all_empty(field, item) and not sh.scheming_field_required(field)
                    for schema_subfield in field['subfields']:
                        if schema_subfield.get('required', False) and not item_is_empty_and_optional:
                            if type(schema_subfield.get('label', '')) is dict:
                                subfield_label = schema_subfield.get('field_name', '') + " " + str(index)
                            else:
                                subfield_label = schema_subfield.get('label', schema_subfield.get('field_name', '')) + " " + str(index)

                            subfield_value = item.get(schema_subfield.get('field_name', ''), "")
                            composite_not_empty_subfield(key, subfield_label , subfield_value, errors)
                    
                    # Call custom author and funder validation for each item
                    author_validator(key , item, index, field, errors)        
                    funder_validator(key , item, index, field, errors)        
                    project_validator(key , item, index, field, errors)        

                # remove empty elements from list
                clean_list = []
                for element in found_list:
                    if not composite_all_empty(field, element):
                        clean_list += [element]
                # dump the list to a string
                data[key] = json.dumps(clean_list, ensure_ascii=False)

                # delete the extras to avoid duplicate fields
                for extra in extras_to_delete:
                    del extras[extra]

        # check if the field is required
        if sh.scheming_field_required(field):
            not_empty(key, data, errors, context)

    return validator

@scheming_validator
@register_validator
def embargo_date_validator(field, schema):
    """
    A validator to ensure the embargo date is later than today's date.
    """
    def validator(key, data, errors, context):
        embargo_date_str = data.get(key, missing)
        if embargo_date_str is missing or embargo_date_str is None or not embargo_date_str.strip():
            return

        try:
            embargo_date = datetime.strptime(embargo_date_str, "%Y-%m-%d").date()
        except ValueError:
            errors[key].append(_('Invalid date format. Please use YYYY-MM-DD.'))
            return

        if embargo_date <= datetime.now().date():
            errors[key].append(_("Embargo date must be later than today's date"))
            return

        if not ((embargo_date - datetime.now().date()).days < 365):
            errors[key].append(_("The embargo date must be less than a year"))

    return validator
