import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import os

from ckanext.igsn_theme.logic import validators
from ckanext.igsn_theme import views
from ckanext.igsn_theme import helpers


# import ckanext.igsn_theme.cli as cli
from ckanext.igsn_theme.logic import (
    action, auth, validators
)

class IgsnThemePlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)

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

