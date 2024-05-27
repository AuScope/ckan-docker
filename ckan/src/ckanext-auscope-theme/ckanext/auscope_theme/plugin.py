import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
from ckanext.auscope_theme import views
from ckanext.auscope_theme import helpers
from ckanext.auscope_theme.logic import (
    action, auth, schema, validation
)


class AuscopeThemePlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IPackageController, inherit=True)
    plugins.implements(plugins.IAuthFunctions)
    plugins.implements(plugins.IActions)
    plugins.implements(plugins.IBlueprint)
    # plugins.implements(plugins.IClick)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IValidators)

    # IConfigurer

    def update_config(self, config_):
        toolkit.add_template_directory(config_, "/shared/templates")
        toolkit.add_template_directory(config_, "templates")
        toolkit.add_public_directory(config_, "/shared/public")
        toolkit.add_public_directory(config_, "public")
        toolkit.add_resource("assets", "auscope_theme")

    # IPackageController

    def after_dataset_show(self, *args, **kwargs):
        return schema.after_dataset_show(*args, **kwargs)

    def after_dataset_update(self, *args, **kwargs):
        return schema.after_dataset_update(*args, **kwargs)

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
        return {
            "location_validator": validation.location_validator,
            "visibility_validator": validation.visibility_validator,
            "composite_repeating_validator" : validation.composite_repeating_validator,
            "embargo_date_validator" : validation.embargo_date_validator
        }

