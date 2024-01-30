from ckan.plugins import toolkit
from ckan.plugins.toolkit import Invalid
import logging
from ckantoolkit import (
    get_validator,
    UnknownValidator,
    missing,
    Invalid,
    StopOnError,
    _,
    unicode_safe,
)

logger = logging.getLogger(__name__)


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
def location_validator(field, schema):
    def validator(key, data, errors, context):
        location_choice = data.get(('location_choice',), [])
        point_latitude = data.get(('point_latitude',), [])
        point_longitude = data.get(('point_longitude',), [])
        bounding_box = data.get(('bounding_box',), [])

        if location_choice == 'point':
            if not point_latitude or not is_valid_latitude(point_latitude):
                errors[('point_latitude',)].append(_("Point latitude is required and must be valid."))
            if not point_longitude or not is_valid_longitude(point_longitude):
                errors[('point_longitude',)].append(_("Point longitude is required and must be valid."))
        
        elif location_choice == 'area':
            if not bounding_box:
                errors[('bounding_box',)].append(_("Bounding box is required."))
            elif not is_valid_bounding_box(bounding_box):
                errors[('bounding_box',)].append(_("Bounding box coordinates are invalid."))

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
        min_lat, min_lng, max_lat, max_lng = map(float, bbox.split(','))

        return all(-90 <= lat <= 90 for lat in [min_lat, max_lat]) and \
               all(-180 <= lng <= 180 for lng in [min_lng, max_lng]) and \
               min_lat < max_lat and min_lng < max_lng
    except (ValueError, TypeError):
        logger.exception("Error in validating bounding box")
        return False
