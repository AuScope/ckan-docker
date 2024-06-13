import ckan.plugins.toolkit as tk


def igsn_theme_get_sum():
    not_empty = tk.get_validator("not_empty")
    convert_int = tk.get_validator("convert_int")

    return {
        "left": [not_empty, convert_int],
        "right": [not_empty, convert_int]
    }

@tk.chained_action
def before_dataset_search(search_params):
    """
    Force private datasets appear in search results
    """
    search_params['include_private'] = 'True'
    return search_params
