import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
from ckanext.doi.lib import metadata as doi_metadata
import os

from ckanext.igsn_theme.logic import validators
from ckanext.igsn_theme import views
from ckanext.igsn_theme import helpers


# import ckanext.igsn_theme.cli as cli
from ckanext.igsn_theme.logic import (
    action, schema, auth, validators
)

import logging

original_build_metadata_dict = doi_metadata.build_metadata_dict


def patched_build_metadata_dict(pkg_dict):
    """
    A patched version of build_metadata_dict to correct language handling and possibly other
    adjustments needed for DOI metadata.
    """
    # Call the original function
    xml_dict = original_build_metadata_dict(pkg_dict)

    # Correct the language field
    xml_dict['language'] = 'en'  # or some other logic to determine the correct language

    # Return the modified metadata dict
    return xml_dict


# Apply the patch
doi_metadata.build_metadata_dict = patched_build_metadata_dict


class IgsnThemePlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IPackageController, inherit=True)

    plugins.implements(plugins.IAuthFunctions)
    plugins.implements(plugins.IActions)
    plugins.implements(plugins.IBlueprint)
    # plugins.implements(plugins.IClick)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IValidators)
    plugins.implements(plugins.ITranslation)

    # ITranslation
    def i18n_domain(self):
        # This should return the extension's name
        return 'igsn_theme'

    def i18n_locales(self):
        # Return a list of locales your extension supports
        return ['en_AU']
        # return ['en']


    def i18n_directory(self):
        # This points to 'ckanext-igsn_theme/ckanext/igsn_theme/i18n'
        # CKAN uses this path relative to the CKAN extensions directory.
        return os.path.join('ckanext', 'igsn_theme', 'i18n')

    # IConfigurer
    def update_config(self, config_):
        toolkit.add_template_directory(config_, '/shared/templates')
        toolkit.add_template_directory(config_, "templates")
        toolkit.add_public_directory(config_, '/shared/public')
        toolkit.add_public_directory(config_, "public")
        toolkit.add_resource("assets", "igsn_theme")


    # IPackageController
    # def process_doi_metadata(self, pkg_dict):
    #     pkg_dict['language_code'] = 'en'

    def before_view(self, pkg_dict):
        pass

    def after_dataset_create(self, context, pkg_dict):
        return action.create_package_relationship(context, pkg_dict)

    def after_dataset_update(self, context, pkg_dict):
        # self.process_doi_metadata(pkg_dict)
        return action.update_package_relationship(context, pkg_dict)

    def after_dataset_delete(self, context, pkg_dict):
        return action.delete_package_relationship(context, pkg_dict)

    def before_dataset_search(self, *args, **kwargs):
        return schema.before_dataset_search(*args, **kwargs)
    
    # IAuthFunctions

    def get_auth_functions(self):
        return auth.get_auth_functions()

    # IActions

    def get_actions(self):
        return action.get_actions()

    # IBlueprint

    def get_blueprint(self):
        return views.get_blueprints()

    # IClick

    # def get_commands(self):
    #     return cli.get_commands()

    # ITemplateHelpers

    def get_helpers(self):
        return helpers.get_helpers()

    # IValidators

    def get_validators(self):
        return validators.get_validators()

