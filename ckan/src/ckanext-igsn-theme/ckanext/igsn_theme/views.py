from flask import Blueprint, request, Response, render_template, redirect, url_for, session , jsonify, render_template_string
from flask.views import MethodView
import requests
import os
from werkzeug.utils import secure_filename
from ckan.plugins.toolkit import get_action, h
import ckan.plugins.toolkit as toolkit
from ckan.common import g

from ckan.common import _, current_user
import ckan.lib.base as base
import ckan.logic as logic
import logging

from io import BytesIO
import json
import pandas as pd
from datetime import date
import re

check_access = logic.check_access
NotAuthorized = logic.NotAuthorized
NotFound = logic.NotFound
ValidationError = logic.ValidationError

log = logging.getLogger(__name__)

try:
    from ckanext.contact.routes import _helpers
    contact_plugin_available = True
except ImportError:
    contact_plugin_available = False
    log.warning("ckanext-contact plugin is not available. The contact form functionality will be disabled.")


igsn_theme = Blueprint("igsn_theme", __name__)

class BatchUploadView(MethodView):

    ALLOWED_EXTENSIONS = {'.xlsx', '.xls'}

    def _prepare(self):
        """
        Prepares the context and checks authorization for creating packages.
        """
        context = {
            'user': current_user.name,
            'auth_user_obj': current_user,
        }
        try:
            check_access('package_create', context)
        except NotAuthorized:
            base.abort(403, _('Unauthorized to create a package'))
        return context

    def process_excel(self, uploaded_file, org_id):
        """
        Processes the Excel file for preview.

        Args:
        uploaded_file (werkzeug.datastructures.FileStorage): The uploaded file object.
        org_id (str): The organization ID.

        Returns:
        dict: Data extracted from the Excel file for preview.
        """
        try:
            content = uploaded_file.read()
            excel_data = BytesIO(content)
            sheets = ["samples", "authors", "related_resources"]
            dfs = {}

            for sheet in sheets:
                excel_data.seek(0)
                try:
                    df = pd.read_excel(excel_data, sheet_name=sheet, na_filter=False, engine="openpyxl")
                    dfs[sheet] = df if not df.empty else pd.DataFrame()
                except Exception as e:
                    dfs[sheet] = pd.DataFrame()
                    print(f"Error processing sheet {sheet}: {str(e)}")

            samples_df = dfs["samples"]
            authors_df = dfs["authors"]
            related_resources_df = dfs["related_resources"]

            # Initialize samples data structure
            samples_data = []

            # Iterate over each row in the samples DataFrame
            for _, row in samples_df.iterrows():
                sample = row.to_dict()

                # Process author_emails
                author_emails = [
                    email.strip() for email in sample.get("author_emails", "").split(";")
                ]
                matched_authors = authors_df[authors_df["author_email"].isin(author_emails)]
                sample["author"] = json.dumps(matched_authors.to_dict("records"))

                # Process related_resources_urls
                related_resource_urls = [
                    url.strip()
                    for url in sample.get("related_resources_urls", "").split(";")
                ]
                matched_resources = related_resources_df[
                    related_resources_df["related_resource_url"].isin(related_resource_urls)
                ]
                sample["related_resource"] = json.dumps(matched_resources.to_dict("records"))

                sample['user_keywords'] = self.validate_user_keywords(sample['user_keywords'])
                sample['publication_date'] = date.today().isoformat()
                sample['owner_org'] = org_id
                sample['notes'] = sample['description']
                sample['location_choice'] = 'noLocation'
                if 'point_latitude' in sample and sample['point_latitude'] != '' and 'point_longitude' in sample and sample['point_longitude'] != '':
                    sample['location_choice'] = 'point'
                    coordinates = [(sample['point_latitude'], sample['point_longitude'])]
                    sample['location_data'] = self.generate_location_geojson(coordinates)

                defaults = {
                    "publisher_identifier_type": "ror",
                    "publisher_identifier": "https://ror.org/04s1m4564",
                    "publisher": "AuScope",
                    "resource_type": "physicalobject",
                }

                sample.update(defaults)
                name= self.generate_sample_name (org_id,sample['material_type'],sample['sample_type'],sample['sample_number']);
                sample["name"] =  name

                samples_data.append(sample)

            return {
                "samples": samples_data,
                "authors": authors_df.to_dict("records"),
                "related_resources": related_resources_df.to_dict("records")
            }

        except Exception as e:
            raise ValueError(f"Failed to read Excel file: {str(e)}")
        
    def generate_sample_name(self,org_id, material_type, sample_type, sample_number):
        
        org_name= self.get_organization_name(org_id)
        org_name = org_name.replace(' ', '_')
        material_type = material_type.replace(' ', '_')
        sample_type = sample_type.replace(' ', '_')
        sample_number = sample_number.replace(' ', '_')
        
        name = f"{org_name}-{material_type}-Sample-{sample_type}-{sample_number}"
        name = re.sub(r'[^a-z0-9-_]', '', name.lower())
        return name    

    def get_organization_name(self , organization_id):
        try:
            organization = get_action('organization_show')({}, {'id': organization_id})
            organization_name = organization['name']
            return organization_name
        except:
            return None
            
    def generate_location_geojson(self, coordinates_list):
        features = []
        for lat, lng in coordinates_list:
            point_feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lng, lat]
                },
                "properties": {}
            }
            features.append(point_feature)

        feature_collection = {
            "type": "FeatureCollection",
            "features": features
        }
        return feature_collection
    
    def validate_user_keywords(self, user_keywords):
        # Regular expression pattern for allowed characters
        pattern = r'^[\w\s.-]+$'
        
        # Check if the user_keywords match the pattern
        if re.match(pattern, user_keywords):
            return user_keywords
        else:
            # Remove any characters that are not allowed
            sanitized_keywords = re.sub(r'[^\w\s.-]', ' ', user_keywords)
            return sanitized_keywords    
    
    def get(self):
        """
        Handles the GET request to show the batch upload form.
        """
        self._prepare()
        org_id = request.args.get('group')
        return render_template('batch/new.html', group=org_id, preview_data={}, file_name="")
    
    def post(self):
        """
        Handles the POST request to upload and process the batch dataset file or submit a URL.
        """
        context = self._prepare()
        org_id = request.args.get('group')
        uploaded_file = request.files.get('file')
        save_option = request.form.get('save')
        preview_option = request.form.get('preview')
        preview_data={}
        file_name=''

        if not org_id:
            h.flash_error(_('No collection is selected.'), 'error')
            return redirect(url_for('igsn_theme.batch_upload')) 

        try:
            if preview_option == 'Preview':
                if not uploaded_file:
                    h.flash_error(_('No file provided.'), 'error')
                    return redirect(url_for('igsn_theme.batch_upload', group=org_id))
                
                file_name = secure_filename(uploaded_file.filename)
                file_extension = os.path.splitext(file_name)[1].lower()
                if file_extension not in self.ALLOWED_EXTENSIONS:
                    h.flash_error(_('Please upload an Excel file (.xlsx or .xls).'), 'error')
                    return redirect(url_for('igsn_theme.batch_upload', group=org_id))       
                           
                preview_data = self.process_excel(uploaded_file, org_id)
                session['preview_data'] = preview_data  
                session['file_name'] = file_name  

                return render_template('batch/new.html', group=org_id, preview_data=preview_data, file_name=file_name)
            
            elif save_option == 'Save':
                preview_data = session.get('preview_data', {})
                file_name = session.get('file_name', '')

                if not preview_data or not preview_data.get('samples'):
                    h.flash_error(_('Please generate a preview first.'), 'error')
                    return redirect(url_for('igsn_theme.batch_upload', group=org_id))
                
                data = preview_data['samples']
                successful_creations = 0
                unsuccessful_creations = 0
                for sample_data in data:
                    try:
                        get_action('package_create')(context, sample_data)
                        successful_creations += 1
                        sample_data['status'] = "created"
                    except Exception as e:
                        unsuccessful_creations += 1
                        sample_data['status'] = "error"
                
                if unsuccessful_creations == 0:
                    session.pop('preview_data', None)  
                    session.pop('file_name', None)  
                    h.flash_success(_('Successfully processed your submission'))
                    return render_template('batch/new.html', group=org_id, preview_data={}, file_name='')
                elif successful_creations == 0:
                        h.flash_error(_('Failed to create any samples.'), 'error')
                        return render_template('batch/new.html', group=org_id, preview_data=preview_data, file_name=file_name)
                else:
                    h.flash_error(f"Successfully created {successful_creations} samples. {unsuccessful_creations} samples failed to create.")
                    return render_template('batch/new.html', group=org_id, preview_data=preview_data, file_name=file_name)
            else:
                h.flash_error(_('Invalid action'), 'error')
                return render_template('batch/new.html', group=org_id, preview_data=preview_data, file_name=file_name)
            
        except NotAuthorized:
            base.abort(403, _('Unauthorized to read package'))
        except NotFound:
            base.abort(404, _('Not Found'))
        except ValidationError as e:
            h.flash_error(_('Validation error: ') + str(e), 'error')
            return render_template('batch/new.html', group=org_id, preview_data=preview_data, file_name=file_name)
        except Exception as e:
            h.flash_error(_('Unexpected error: ') + str(e), 'error')
            return render_template('batch/new.html', group=org_id, preview_data=preview_data, file_name=file_name)

        return render_template('batch/new.html', group=org_id, preview_data=preview_data, file_name=file_name)



def page():
    return "Hello, igsn_theme!"


igsn_theme.add_url_rule("/igsn_theme/page", view_func=page)


igsn_theme.add_url_rule(
    '/batch_upload',
    view_func=BatchUploadView.as_view('batch_upload'),
    methods=['GET', 'POST']
)

@igsn_theme.route('/get_preview_data', methods=['GET'])
def get_preview_data():
    """
    Endpoint to fetch the preview data.
    """
    preview_data = session.get('preview_data', {})
    return jsonify(preview_data)

@igsn_theme.route('/remove_preview_data', methods=['POST'])
def remove_preview_data():
    """
    Endpoint to remove the preview data.
    """
    session.pop('preview_data', None) 
    session.pop('file_name', None) 
    return "Preview data removed successfully", 200

@igsn_theme.route('/organization/request_new_collection', methods=['GET', 'POST'])
def request_new_collection():
    """
    Form based interaction for requesting a new collection.
    """
    if not g.user:
        toolkit.abort(403, toolkit._('Unauthorized to send request'))

    extra_vars = {
        'data': {},
        'errors': {},
        'error_summary': {},
    }
    try:
        if toolkit.request.method == 'POST':
            email_body = generate_new_collection_email_body(request)
            request.values = request.values.copy()
            request.values['content'] = email_body
            
            if contact_plugin_available:
                result = _helpers.submit()
                if result.get('success', False):
                    return toolkit.render('contact/success.html')
                else:
                    if result.get('recaptcha_error'):
                        toolkit.h.flash_error(result['recaptcha_error'])
                    extra_vars.update(result)
            else:
                toolkit.h.flash_error(toolkit._('Contact functionality is currently unavailable.'))
                return toolkit.redirect_to('/organization')
        else:
            try:
                extra_vars['data']['name'] = g.userobj.fullname or g.userobj.name
                extra_vars['data']['email'] = g.userobj.email
            except AttributeError:
                extra_vars['data']['name'] = extra_vars['data']['email'] = None

        return toolkit.render('contact/req_new_collection.html', extra_vars=extra_vars)

    except Exception as e:
        toolkit.h.flash_error(toolkit._('An error occurred while processing your request.'))
        logger = logging.getLogger(__name__)
        logger.error('An error occurred while processing your request: {}'.format(str(e)))
        return toolkit.abort(500, toolkit._('Internal server error'))

@igsn_theme.route('/organization/request_join_collection', methods=['GET', 'POST'])
def request_join_collection():
    """
    Form based interaction for requesting to jon in a collection.
    """
    if not g.user:
        toolkit.abort(403, toolkit._('Unauthorized to send request'))

    org_id = toolkit.request.args.get('org_id')
    org_name = toolkit.request.args.get('org_name')

    extra_vars = {
        'data': {},
        'errors': {},
        'error_summary': {},
    }
    try: 
        if toolkit.request.method == 'POST':

            email_body = generate_join_collection_email_body(request, org_id,org_name)
            request.values = request.values.copy()
            request.values['content'] = email_body

            if contact_plugin_available:               
                result = _helpers.submit()
                if result.get('success', False):
                    return toolkit.render('contact/success.html')
                else:
                    if result.get('recaptcha_error'):
                        toolkit.h.flash_error(result['recaptcha_error'])
                    extra_vars.update(result)
            else:
                toolkit.h.flash_error(toolkit._('Contact functionality is currently unavailable.'))
                return toolkit.redirect_to('/organization')
        else:
            try:
                extra_vars['data']['name'] = g.userobj.fullname or g.userobj.name
                extra_vars['data']['email'] = g.userobj.email
                extra_vars['data']['collection_id'] = org_id
                extra_vars['data']['collection_name'] = org_name

            except AttributeError:
                extra_vars['data']['name'] = extra_vars['data']['email'] = None

        return toolkit.render('contact/req_join_collection.html', extra_vars=extra_vars)
    except Exception as e:
        toolkit.h.flash_error(toolkit._('An error occurred while processing your request.'))
        logger = logging.getLogger(__name__)
        logger.error('An error occurred while processing your request: {}'.format(str(e)))
        return toolkit.abort(500, toolkit._('Internal server error'))
 

def generate_new_collection_email_body(request):
    data = {
        'name': request.values.get('name'),
        'email': request.values.get('email'),
        'collection_full_name': request.values.get('collection_full_name'),
        'collection_short_name': request.values.get('collection_short_name'),
        'description': request.values.get('description')
    }    
    email_body_template = """
    Hello,

    A new collection request has been submitted. Here are the details:

    Contact Name: {{ data.name }}
    Contact Email: {{ data.email }}
    
    Collection Details:
    - Full Name: {{ data.collection_full_name }}
    - Short Name: {{ data.collection_short_name }}
    
    Description of the Collection:
    {{ data.description }}

    Best regards,
    [Your Organization Name]
    """
    return render_template_string(email_body_template, data=data)

def generate_join_collection_email_body(request,org_id,org_name):
    data = {
        'name': request.values.get('name'),
        'email': request.values.get('email'),
        'description': request.values.get('description'),
        'collection_id': org_id,
        'collection_name': org_name
    }

    email_body_template = """
    Hello,

    You have received a new request to join the collection. Below are the details of the request:

    Contact Name: {{ data.name }}
    Contact Email: {{ data.email }}

    Description of Request:
    {{ data.description }}

    Collection Details:
    - Collection ID: {{ data.collection_id }}
    - Collection Name: {{ data.collection_name }}

    """
    return render_template_string(email_body_template, data=data)


# Add the proxy route
@igsn_theme.route('/api/proxy/fetch_epsg', methods=['GET'])
def fetch_epsg():
    page = request.args.get('page', 0)
    keywords = request.args.get('keywords', '')
    external_url = f'https://apps.epsg.org/api/v1/CoordRefSystem/?includeDeprecated=false&pageSize=50&page={page}&keywords={keywords}'

    response = requests.get(external_url)
    if response.ok:
        return Response(response.content, content_type=response.headers['Content-Type'], status=response.status_code)
    else:
        return {"error": "Failed to fetch EPSG codes"}, 502

def get_blueprints():
    return [igsn_theme]