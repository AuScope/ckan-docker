import ckan.plugins.toolkit as tk
from ckantoolkit import ( _, missing , get_validator )
import json

import ckanext.scheming.helpers as sh
import ckan.lib.navl.dictization_functions as df

from ckanext.scheming.validation import scheming_validator, register_validator
import logging

from ckan.logic.validators import owner_org_validator as ckan_owner_org_validator
from ckan.authz import users_role_for_group_or_org
from pprint import pformat

import geojson
from shapely.geometry import shape, mapping

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

        log = logging.getLogger(__name__)
        try:
            log.debug("location_data: %s", location_data)
            
            geom = shape(location_data['features'][0]['geometry'])
            log.debug("WKT for spatial field: %s", geom.wkt)
            
            geojson_geom = geojson.dumps(mapping(geom))
            log.debug("GeoJSON for spatial field: %s", geojson_geom)
            
            data['spatial',] = geojson_geom


            log.debug("Data after setting spatial: %s", pformat(data))

        except Exception as e:
            log.error("Error processing GeoJSON: %s", e)
            add_error(location_data_key, f"Error processing GeoJSON: {e}")

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

def igsn_theme_required(value):
    if not value or value is tk.missing:
        raise tk.Invalid(tk._("Required"))
    return value

def owner_org_validator(key, data, errors, context):
    owner_org = data.get(key)

    if owner_org is not tk.missing and owner_org is not None and owner_org != '':
        if context.get('auth_user_obj', None) is not None:
            username = context['auth_user_obj'].name
        else:
            username = context['user']
        role = users_role_for_group_or_org(owner_org, username)
        if role == 'member':
            return
    ckan_owner_org_validator(key, data, errors, context)

def get_validators():
    return {
        "igsn_theme_required": igsn_theme_required,
        "location_validator": location_validator,
        "composite_repeating_validator": composite_repeating_validator,
        "owner_org_validator": owner_org_validator,
    }
