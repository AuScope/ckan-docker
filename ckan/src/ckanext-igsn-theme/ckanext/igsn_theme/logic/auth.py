import ckan.plugins.toolkit as tk


@tk.auth_allow_anonymous_access
def igsn_theme_get_sum(context, data_dict):
    return {"success": True}


def get_auth_functions():
    return {
        "igsn_theme_get_sum": igsn_theme_get_sum,
    }
