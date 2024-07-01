import ckan.plugins.toolkit as tk
import ckanext.igsn_theme.logic.schema as schema
import ckan.lib.plugins as lib_plugins
from ckan.logic.validators import owner_org_validator as default_owner_org_validator
import logging
from pprint import pformat
import re
import ckan.model as model
import json

try:
    import ckanext.dcat.logic.action as dcat_actions
    dcat_plugin_available = True
except ImportError:
    dcat_plugin_available = False
    log = logging.getLogger(__name__)
    log.warning("ckanext-dcat plugin is not available. The dcat form functionality will be disabled.")


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
def organization_list_for_user(next_action, context, data_dict):
    # Allow all users to see organization list
    perm = data_dict.get('permission')
    if perm in ['create_dataset', 'update_dataset', 'delete_dataset']:
        data_dict = {**data_dict, **{'permission': 'read'}}
    return next_action(context, data_dict)

@tk.chained_action
def package_create(next_action, context, data_dict):
    logger = logging.getLogger(__name__)
    logger.info("package_create before data_dict: %s", pformat(data_dict))
    
    package_type = data_dict.get('type')
    package_plugin = lib_plugins.lookup_package_plugin(package_type)
    if 'schema' in context:
        schema = context['schema']
    else:
        schema = package_plugin.create_package_schema()
    # Replace owner_org_validator
    if 'owner_org' in schema:
        schema['owner_org'] = [
            owner_org_validator if f is default_owner_org_validator else f
            for f in schema['owner_org']
        ]

    data_dict['name'] = generate_sample_name(data_dict)    
    generate_parent_related_resource(data_dict)

    logger.info("package_create after data_dict: %s", pformat(data_dict))

    return next_action(context, data_dict)

@tk.chained_action
def package_update(next_action, context, data_dict):
    # logger = logging.getLogger(__name__)
    # logger.info("package_update data_dict: %s", pformat(data_dict))
    
    data_dict['name'] = generate_sample_name(data_dict)
    update_parent_related_resource(data_dict)
    return next_action(context, data_dict)


def generate_sample_name(data_dict):
    
    owner_org=data_dict['owner_org']
    material_type = data_dict['material_type']
    sample_type = data_dict['sample_type']
    sample_number = data_dict['sample_number']
    org_name= tk.get_action('organization_show')({}, {'id': owner_org})['name']
    org_name = org_name.replace(' ', '_')
    material_type = material_type.replace(' ', '_')
    sample_type = sample_type.replace(' ', '_')
    sample_number = sample_number.replace(' ', '_')
    
    name = f"{org_name}-{material_type}-Sample-{sample_type}-{sample_number}"
    name = re.sub(r'[^a-z0-9-_]', '', name.lower())
    return name

def generate_parent_related_resource(data_dict):
    parent_id = data_dict.get('parent')    
    if parent_id:
        parent = tk.get_action('package_show')({}, {'id': parent_id})        
        highest_index = -1
        for key in data_dict.keys():
            if key.startswith('related_resource-'):
                parts = key.split('-')
                if len(parts) > 1 and parts[1].isdigit():
                    index = int(parts[1])
                    if index > highest_index:
                        highest_index = index
        
        new_index = highest_index + 1
        
        data_dict[f'related_resource-{new_index}-related_resource_type'] = "physicalobject"
        data_dict[f'related_resource-{new_index}-related_resource_title'] = parent.get('title')
        data_dict[f'related_resource-{new_index}-relation_type'] = "IsDerivedFrom"

        doi_value = parent.get('doi')
        if doi_value:
            if 'https' not in doi_value:
                doi_value = "https://doi.org/" + doi_value           
            data_dict[f'related_resource-{new_index}-related_resource_url'] = doi_value

def update_parent_related_resource(data_dict):
    logger = logging.getLogger(__name__)

    parent_id = data_dict.get('parent')

    if parent_id:
        try:
            parent = tk.get_action('package_show')({}, {'id': parent_id})
        except Exception as e:
            logger.error(f"Error fetching parent package: {e}")
            return

        keys_to_delete = []
        related_resource_indices = [key.split('-')[1] for key in data_dict.keys() if key.startswith('related_resource-') and '-related_resource_type' in key]

        for index in related_resource_indices:
            resource_type_key = f'related_resource-{index}-related_resource_type'
            relation_type_key = f'related_resource-{index}-relation_type'

            if data_dict.get(resource_type_key) == 'physicalobject' and data_dict.get(relation_type_key) == 'IsDerivedFrom':
                keys_to_delete.extend([key for key in data_dict.keys() if key.startswith(f'related_resource-{index}-')])

        for key in keys_to_delete:
            del data_dict[key]

        if 'related_resource' in data_dict:
            try:
                related_resources = json.loads(data_dict['related_resource'])
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON string for related_resource: {e}")
                related_resources = []
        else:
            related_resources = []

        highest_index = -1
        for key in data_dict.keys():
            if key.startswith('related_resource-'):
                parts = key.split('-')
                if len(parts) > 1 and parts[1].isdigit():
                    index = int(parts[1])
                    if index > highest_index:
                        highest_index = index

        new_index = highest_index + 1
        new_resource = {
            'related_resource_type': 'physicalobject',
            'related_resource_title': parent.get('title'),
            'relation_type': 'IsDerivedFrom',
            'related_resource_url': None
        }

        doi_value = parent.get('doi')
        if doi_value:
            if 'https' not in doi_value:
                doi_value = "https://doi.org/" + doi_value
            new_resource['related_resource_url'] = doi_value

        if related_resources:
            related_resources.append(new_resource)
            data_dict['related_resource'] = json.dumps(related_resources)
        else:
            data_dict[f'related_resource-{new_index}-related_resource_type'] = new_resource['related_resource_type']
            data_dict[f'related_resource-{new_index}-related_resource_title'] = new_resource['related_resource_title']
            data_dict[f'related_resource-{new_index}-relation_type'] = new_resource['relation_type']
            if new_resource['related_resource_url']:
                data_dict[f'related_resource-{new_index}-related_resource_url'] = new_resource['related_resource_url']

    else:
        logger.warning("No parent ID provided")


# We do not need user_create customization here.
# Users do not need to be a part of an organization by default.
@tk.chained_action
def user_create(next_action, context, data_dict):
    email = data_dict.get('email', '').lower()
    data_dict['email'] = email
    return next_action(context, data_dict)


@tk.chained_action
def user_invite(next_action, context, data_dict):
    email = data_dict.get('email', '').lower()
    data_dict['email'] = email
    return next_action(context, data_dict)

@tk.chained_action
def package_search(next_action, context, data_dict):
    """
    Overwrite package_search so that it will ignore auth so all results are returned
    """
    context['ignore_auth'] = True
    return next_action(context, data_dict)

def create_package_relationship(context, pkg_dict):
    if 'parent' in pkg_dict and pkg_dict['parent']:
        logger = logging.getLogger(__name__)
        parent_id = pkg_dict['parent']
        try:
            tk.get_action('package_relationship_create')(context, {
                'subject': pkg_dict['id'],
                'object': parent_id,
                'type': 'child_of',
                'comment': 'Creating a child_of relationship'
            })
        except Exception as e:
            logger.error('Failed to create package relationship: {}'.format(str(e)))

def update_package_relationship(context, pkg_dict):
    """
    Updates the parent relationship of a package.

    Parameters:
    context (dict): The context dictionary containing user and auth details.
    pkg_dict (dict): Dictionary containing the package details, including 'id' and optional 'parent'.

    Returns:
    None
    """
    logger = logging.getLogger(__name__)

    if 'parent' in pkg_dict and pkg_dict['parent']:
        parent_id = pkg_dict['parent']
        package_id = pkg_dict['id']
        relationship_type = 'child_of'

        try:
            existing_relationships = tk.get_action('package_relationships_list')(
                context, {'id': package_id, 'rel': relationship_type}
            )

            for rel in existing_relationships:
                try:
                    tk.get_action('package_relationship_delete')(context, {
                        'subject': package_id,
                        'object': rel['object'],
                        'type': relationship_type
                    })
                except Exception as e:
                    logger.error(f"Error while deleting relationship {package_id} child_of {rel['object']}: {str(e)}")

        except tk.ObjectNotFound:
            logger.info(f"No existing relationships found for package {package_id}")

        except Exception as e:
            logger.error(f"Error while retrieving relationships for package {package_id}: {str(e)}")
            return

        try:
            tk.get_action('package_relationship_create')(context, {
                'subject': package_id,
                'object': parent_id,
                'type': relationship_type,
                'comment': 'Updated relationship to new parent'
            })
        except Exception as e:
            logger.error(f"Error while creating relationship for package {package_id}: {str(e)}")


def delete_package_relationship(context, pkg_dict):
    logger = logging.getLogger(__name__)
    package_id = pkg_dict['id']
    try:
        existing_relationships = tk.get_action('package_relationships_list')(context, {'id': package_id})
        for rel in existing_relationships:
            tk.get_action('package_relationship_delete')(context, rel)
    except Exception as e:
        logger.error(f"Failed to delete package relationship: {str(e)}")

@tk.chained_action
def dcat_dataset_show(next_action,context, data_dict):
    logger = logging.getLogger(__name__)

    if not dcat_plugin_available:
        raise tk.ObjectNotFound("ckanext-dcat plugin is not available.")
        
    logger.info('custom_dcat_dataset_show called with context: %s, data_dict: %s', context, data_dict)

    context['ignore_auth'] = True

    logger.info('Modified context: %s', context)
    
    result = next_action(context, data_dict)

    logger.info('Result: %s', result)

    return result


def get_actions():
    return {
        'igsn_theme_get_sum': igsn_theme_get_sum,
        'organization_list_for_user': organization_list_for_user,
        'package_create': package_create,
        'user_create': user_create,
        'user_invite': user_invite,
        'create_package_relationship' : create_package_relationship,
        'update_package_relationship' : update_package_relationship,
        'delete_package_relationship' : delete_package_relationship,
        'package_update' : package_update,
        'package_search': package_search,
        'dcat_dataset_show': dcat_dataset_show

    }
