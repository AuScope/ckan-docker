import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit

from ckanext.igsn_theme.logic import validators
from ckanext.igsn_theme import views
from ckanext.igsn_theme import helpers


# import ckanext.igsn_theme.cli as cli
# from ckanext.igsn_theme.logic import (
#     action, auth, validators
# )


class IgsnThemePlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    
    # plugins.implements(plugins.IAuthFunctions)
    # plugins.implements(plugins.IActions)
    plugins.implements(plugins.IBlueprint)
    # plugins.implements(plugins.IClick)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IValidators)
    

    # IConfigurer

    def update_config(self, config_):
        toolkit.add_template_directory(config_, '/shared/templates')
        toolkit.add_template_directory(config_, "templates")
        toolkit.add_public_directory(config_, '/shared/public')
        toolkit.add_public_directory(config_, "public")
        toolkit.add_resource("assets", "igsn_theme")

    
    # IAuthFunctions

    # def get_auth_functions(self):
    #     return auth.get_auth_functions()

    # IActions

    # def get_actions(self):
    #     return action.get_actions()

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
    
