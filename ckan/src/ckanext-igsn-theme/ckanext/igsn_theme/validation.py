from ckantoolkit import (get_validator, _)


# A dictionary to store your validators
all_validators = {}

def register_validator(fn):
    """
    collect validator functions into ckanext.scheming.all_helpers dict
    """
    all_validators[fn.__name__] = fn
    return fn

ignore_missing = get_validator('ignore_missing')
not_empty = get_validator('not_empty')

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
def conditional_required_validator(value, context):
    def validator(key, data, errors, context):
        # Hypothetical function to determine if the condition for requiring the field is met
        if should_field_be_required(context):
            return not_empty(key, data, errors, context)
        else:
            return ignore_missing(key, data, errors, context)

    return validator

def should_field_be_required(context):

    # Pseudocode: Check if the package is in draft or what the current form page is
    # This part needs customization based on your application's logic and state management
    draft_status = context.get('draft_status', False)
    current_page = context.get('form_page', None)

    # Logic to determine if the field should be required
    if draft_status or (current_page and current_page == 'specific_page'):
        return True
    return False

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
            # Ensure noLocation related fields are not processed further
            for key in [point_latitude_key, point_longitude_key, bounding_box_key]:
                data[key] = None
            return ignore_missing(key, data, errors, context)

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
