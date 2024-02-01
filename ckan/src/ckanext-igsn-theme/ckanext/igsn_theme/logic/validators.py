import ckan.plugins.toolkit as tk


def igsn_theme_required(value):
    if not value or value is tk.missing:
        raise tk.Invalid(tk._("Required"))
    return value


def get_validators():
    return {
        "igsn_theme_required": igsn_theme_required,
    }
