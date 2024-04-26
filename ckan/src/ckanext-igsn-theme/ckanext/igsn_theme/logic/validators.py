import ckan.plugins.toolkit as tk
from ckantoolkit import ( _, missing , get_validator )
import json

import ckanext.scheming.helpers as sh
import ckan.lib.navl.dictization_functions as df

from ckanext.scheming.validation import scheming_validator, register_validator
import logging
from ckan.logic.validators import owner_org_validator as ckan_owner_org_validator
from ckan.authz import users_role_for_group_or_org

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

StopOnError = df.StopOnError
not_empty = get_validator('not_empty')

# A dictionary to store your validators
all_validators = {}



@scheming_validator
@register_validator
def location_validator(field, schema):
    def validator(key, data, errors, context):
        missing_error = _("Missing value")
        invalid_error = _("Invalid value")

        location_choice_key = ('location_choice',)
        point_latitude_key = ('point_latitude',)
        point_longitude_key = ('point_longitude',)
        bounding_box_key = ('bounding_box',)
        epsg_code_key = ('epsg_code',)

        location_choice = data.get(location_choice_key, missing)
        point_latitude = data.get(point_latitude_key, missing)
        point_longitude = data.get(point_longitude_key, missing)
        bounding_box = data.get(bounding_box_key, missing)
        epsg_code = data.get(epsg_code_key, missing)

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
        
        if epsg_code is missing:
            add_error(epsg_code_key, missing_error)
               
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
    ''' Function equivalent to ckan.lib.navl.validators.not_empty
         but for subfields (custom message including subfield)
    '''
    if not value or value is missing:
        errors[key].append(_('Missing value at required subfield ' + subfield_label))
        raise StopOnError


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

def igsn_theme_required(value):
    if not value or value is tk.missing:
        raise tk.Invalid(tk._("Required"))
    return value

def get_validators():
    return {
        "igsn_theme_required": igsn_theme_required,
        "location_validator": location_validator,
        "composite_repeating_validator": composite_repeating_validator,
    }