import ckan.plugins.toolkit as tk
import ckanext.igsn_theme.logic.schema as schema


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
def package_create(next_action, context, data_dict):
    package_type = data_dict.get('type')
    
    # Replace owner_org_validator
    
    return next_action(context, data_dict)

def get_actions():
    return {
        'igsn_theme_get_sum': igsn_theme_get_sum,
        'package_create': package_create,
    }
