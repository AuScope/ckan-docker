import os
from flask import Blueprint, request, Response, render_template, redirect, url_for, flash, jsonify
from flask.views import MethodView
import requests
import re
from ckan.plugins.toolkit import h
import ckan.plugins.toolkit as toolkit

from ckan.common import _, g, current_user
import ckan.lib.base as base
import ckan.logic as logic
import random
import pandas as pd
import json

from io import BytesIO
# Only import what's needed and avoid duplications
check_access = logic.check_access
NotAuthorized = logic.NotAuthorized
NotFound = logic.NotFound
ValidationError = logic.ValidationError

igsn_theme = Blueprint("igsn_theme", __name__)

class BatchUploadView(MethodView):
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

    def get(self):
        """
        Handles the GET request to show the batch upload form.
        """
        self._prepare()  
        return render_template('batch/new.html')

    async def post(self):
        """
        Handles the POST request to upload and process the batch dataset file.
        """
        context = self._prepare()
        
        
        uploaded_file = request.files.get('file')
        if not uploaded_file:
            h.flash_error(_('No file uploaded.'))
            return redirect(url_for('igsn_theme.batch_upload'))
        try:
            if uploaded_file:
                file_name = uploaded_file.filename
                file_extension = os.path.splitext(file_name)[1].lower()
                if file_extension not in ['.xlsx', '.xls']:
                    flash('Please upload an Excel file (.xlsx or .xls).', 'error')
                    return redirect(url_for('igsn_theme.batch_upload'))  
                print(f"Processing uploaded file: {file_name}")
                data = process_excel(uploaded_file)
                results = []
                for package_data in data:
                    package = create_package(context, package_data)
                    results.append(package)
                return redirect(url_for('igsn_theme.batch_upload')) 
        except NotAuthorized:
            base.abort(403, _('Unauthorized to read package'))
        except NotFound:
            base.abort(404, _('Dataset not found'))
        except ValidationError as e:
            h.flash_error(_('Validation error: ') + str(e))
            return self.get()
        except Exception as e:
            h.flash_error(_('Failed to process uploaded file: ') + str(e))
            return redirect(url_for('igsn_theme.batch_upload'))


def page():
    return "Hello, igsn_theme!"


igsn_theme.add_url_rule("/igsn_theme/page", view_func=page)

igsn_theme.add_url_rule(
    '/batch_upload', 
    view_func=BatchUploadView.as_view('batch_upload'),
    methods=['GET', 'POST']
)

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

def process_excel(file):
    try:
        # Read the content of the uploaded file into a BytesIO object
        content = file.read()        
        excel_data = BytesIO(content)
        sheets = ["samples", "authors", "related_resources"]
        dfs = {}
        for sheet in sheets:
            excel_data.seek(0)  # Reset file pointer to the beginning
            dfs[sheet] = pd.read_excel(excel_data, sheet_name=sheet, na_filter=False, engine="openpyxl")
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
            sample['user_keywords'] = validate_user_keywords(sample['user_keywords'])
            defaults = {
                "publisher_identifier_type": "ror",
                "publisher_identifier": "https://ror.org/04s1m4564",
                "publication_date": "2024-03-08",
                "notes": "A long description of my dataset",
                "publisher": "AuScope",
                "resource_type": "physicalobject",
                "owner_org": "testing",
                "location_choice": "noLocation"
            }
            sample.update(defaults)
            
            sample["name"] = "ckan-api-test-" + str(random.randint(0, 10000))
            samples_data.append(sample)
        return samples_data
    except ValueError as e:
        raise ValueError(f"Failed to process Excel file: {e}")
    except Exception as e:
        raise Exception(f"Failed to process Excel file: {e}")
def validate_user_keywords(user_keywords):
    # Regular expression pattern for allowed characters
    pattern = r'^[\w\s.-]+$'
    
    # Check if the user_keywords match the pattern
    if re.match(pattern, user_keywords):
        return user_keywords
    else:
        # Remove any characters that are not allowed
        sanitized_keywords = re.sub(r'[^\w\s.-]', ' ', user_keywords)
        return sanitized_keywords
    
def create_package(context, package_data):
    try:
        # Call the package_create action function
        package = toolkit.get_action('package_create')(context, package_data)
        print(f"Package created successfully with ID: {package['id']}")
        return package
    except toolkit.ValidationError as e:
        print(f"Failed to create package. Validation error: {e}")
        raise
    except Exception as e:
        print(f"Failed to create package. Error: {e}")
        raise