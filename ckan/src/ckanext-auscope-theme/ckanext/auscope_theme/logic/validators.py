import ckan.plugins.toolkit as tk
from ckan.authz import users_role_for_group_or_org
from ckan.logic.validators import owner_org_validator as ckan_owner_org_validator


def auscope_theme_required(value):
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
        "auscope_theme_required": auscope_theme_required,
        "owner_org_validator": owner_org_validator,
    }

