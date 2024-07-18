from flask import Blueprint, request, Response, render_template, redirect, url_for, session , jsonify, render_template_string
from flask.views import MethodView
import requests
import os
from werkzeug.utils import secure_filename
from ckan.plugins.toolkit import get_action, h
import ckan.plugins.toolkit as toolkit
from ckan.common import g
from ckan.model import Session
from ckan.common import _, current_user
import ckan.lib.base as base
import ckan.logic as logic
import logging
from ckanext.igsn_theme.logic import (
    action, 
)
from io import BytesIO
import json
import pandas as pd
from datetime import date
import re
from pprint import pformat
import ckan.lib.mailer as mailer
from ckan.common import config

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
            logger = logging.getLogger(__name__)
            content = uploaded_file.read()
            excel_data = BytesIO(content)
            sheets = ["samples", "authors", "related_resources", "funding"]
            dfs = self.read_excel_sheets(excel_data, sheets)
            
            samples_df = dfs["samples"]
            authors_df = dfs["authors"]
            related_resources_df = dfs["related_resources"]
            funding_df = dfs["funding"]
            
            try:
                self.validate_samples(samples_df)
            except Exception as e:
                raise ValueError(f"Validation error in validate_samples: {str(e)}")
            
            try:
                self.validate_authors(authors_df)
            except Exception as e:
                raise ValueError(f"Validation error in validate_authors: {str(e)}")
            
            try:
                self.validate_related_resources(related_resources_df)
            except Exception as e:
                raise ValueError(f"Validation error in validate_related_resources: {str(e)}")
            
            try:
                self.validate_parent(samples_df)
            except Exception as e:
                raise ValueError(f"Validation error in validate_parent: {str(e)}")
            
            samples_data = self.prepare_samples_data(samples_df, authors_df, related_resources_df, funding_df, org_id)
            

            return_value = {
                "samples": samples_data,
                "authors": authors_df.to_dict("records"),
                "related_resources": related_resources_df.to_dict("records"),
                "funders": funding_df.to_dict("records")

            }  
            return return_value

        except Exception as e:
            raise ValueError(f"Failed to read Excel file: {str(e)}")
        
    def generate_sample_name(self,org_id, sample_type, sample_number):
        
        org_name= self.get_organization_name(org_id)
        org_name = org_name.replace(' ', '_')
        sample_type = sample_type.replace(' ', '_')
        sample_number = sample_number.replace(' ', '_')
        
        name = f"{org_name}-{sample_type}-Sample-{sample_number}"
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
    
    def read_excel_sheets(self, excel_data, sheets):
        dfs = {}
        for sheet in sheets:
            excel_data.seek(0)
            try:
                df = pd.read_excel(excel_data, sheet_name=sheet, na_filter=False, engine="openpyxl")
                dfs[sheet] = df if not df.empty else pd.DataFrame()
            except Exception as e:
                dfs[sheet] = pd.DataFrame()
                print(f"Error processing sheet {sheet}: {str(e)}")
        return dfs
          
    def prepare_samples_data(self, samples_df, authors_df, related_resources_df, funding_df, org_id):
        samples_data = []
        for _, row in samples_df.iterrows():
            sample = row.to_dict()
            sample["author"] = self.process_author_emails(sample, authors_df)
            sample["related_resource"] = self.process_related_resources(sample, related_resources_df)
            sample["funder"] = self.process_funding_info(sample, funding_df)

            sample['user_keywords'] = self.validate_user_keywords(sample['user_keywords'])
            sample['publication_date'] = date.today().isoformat()
            sample['private']=False
            sample['notes'] = sample['description']
            sample['location_choice'] = 'noLocation'
            sample['parent_sample'] = sample['parent_sample']

            org = toolkit.get_action('organization_show')({}, {'id': org_id})
            sample['owner_org'] = org_id
            sample['sample_repository_contact_name'] = org.get('contact_name', '')
            sample['sample_repository_contact_email'] = org.get('contact_email', '')
            
            if 'point_latitude' in sample and sample['point_latitude'] != '' and 'point_longitude' in sample and sample['point_longitude'] != '':
                if not self.is_numeric(sample['point_latitude']) or not self.is_numeric(sample['point_longitude']):
                    raise ValueError("Latitude and Longitude must be numeric.")
                sample['location_choice'] = 'point'
                coordinates = [(sample['point_latitude'], sample['point_longitude'])]
                sample['location_data'] = self.generate_location_geojson(coordinates)
            sample['epsg'] = self.get_epsg_name(sample['epsg_code'])
            defaults = {
                "publisher_identifier_type": "ROR",
                "publisher_identifier": "https://ror.org/04s1m4564",
                "publisher": "AuScope",
                "resource_type": "PhysicalObject",
            }
            sample.update(defaults)
            sample["name"] = self.generate_sample_name(org_id, sample['sample_type'], sample['sample_number'])
            samples_data.append(sample)

        return samples_data
    
    def process_author_emails(self, sample, authors_df):
        author_emails = [email.strip() for email in sample.get("author_emails", "").split(";")]
        matched_authors = authors_df[authors_df["author_email"].isin(author_emails)]
        return json.dumps(matched_authors.to_dict("records"))

    def process_related_resources(self, sample, related_resources_df):
        related_resources_urls = sample.get("related_resources_urls")
        if self.is_cell_empty(related_resources_urls):
            return "[]"
        
        related_resource_urls = [url.strip() for url in related_resources_urls.split(";")]
        for url in related_resource_urls:
            self.is_url(url)  # Check if the URL is valid
            related_resources = related_resources_df[related_resources_df['related_resource_url'] == url]
            required_fields = ['related_resource_type', 'related_resource_url', 'related_resource_title', 'relation_type']
            if related_resources[required_fields].map(self.is_cell_empty).any().any():
                raise ValueError(f"Missing required fields for related resource URL: {url}")

        matched_resources = related_resources_df[related_resources_df["related_resource_url"].isin(related_resource_urls)]
        return json.dumps(matched_resources.to_dict("records"))

    def process_funding_info(self, sample, funding_df):
        if not self.is_cell_empty(sample.get("project_ids")):
            project_ids = [project_id.strip() for project_id in sample.get("project_ids").split(";")]
            for project_id in project_ids:
                funding_info = funding_df[funding_df['project_identifier'] == project_id]
                if funding_info.empty:
                    raise ValueError(f"Missing funding information for project ID: {project_id}")
                for _, row in funding_info.iterrows():
                    if self.is_cell_empty(row["funder_name"]):
                        raise ValueError(f"Row for project ID {project_id} must include a funder_name")
                    if not self.is_cell_empty(row["funder_identifier"]) and self.is_cell_empty(row["funder_identifier_type"]):
                        raise ValueError(f"Row for project ID {project_id} with funder_identifier must include funder_identifier_type")
                    if not self.is_cell_empty(row["funder_name"]):
                        if self.is_cell_empty(row["project_name"]) or self.is_cell_empty(row["project_identifier"]) or self.is_cell_empty(row["project_identifier_type"]):
                            raise ValueError(f"Row for funder_name {row['funder_name']} must include project_name, project_identifier, and project_identifier_type")

            matched_funder = funding_df[funding_df["project_identifier"].isin(project_ids)]
            return json.dumps(matched_funder.to_dict("records"))

            # matched_funder_name = funding_df.loc[funding_df["project_identifier"].isin(project_ids), "funder_name"]
            # return matched_funder_name.tolist()
        return "[]"
    
    def validate_samples(self, samples_df):
        samples_columns_to_check = ['sample_number', 'description', 'user_keywords', 'sample_type', 'author_emails']
        self.check_required_fields(samples_df, samples_columns_to_check)
        self.check_unique_sample_number(samples_df)
        self.validate_epsg(samples_df)
        
    def check_required_fields(self, df, columns_to_check):
        empty_check = df[columns_to_check].isna() | (df[columns_to_check] == '')
        missing_fields = {}

        for col in columns_to_check:
            missing_in_col = empty_check[col]
            if missing_in_col.any():
                missing_fields[col] = df[missing_in_col].index.tolist()

        if missing_fields:
            error_messages = [f"Missing values in column '{col}': rows {indexes}" for col, indexes in missing_fields.items()]
            raise ValueError(" | ".join(error_messages))

    def check_unique_sample_number(self, samples_df):
        duplicates = samples_df[samples_df['sample_number'].duplicated(keep=False)]
        if not duplicates.empty:
            duplicate_values = duplicates['sample_number'].value_counts()
            # Raise an error with a message containing the duplicate values
            raise ValueError(f"Duplicate sample numbers detected: {duplicate_values.index.tolist()}")
        
    def validate_authors(self, authors_df):
        columns_to_check = ['author_email', 'author_name', 'author_affiliation', 'author_name_type']
        valid_identifier_types = ["ORCID", "ISNI", "LCNA", "VIAF", "GND", "DAI", "ResearcherID", "ScopusID", "Other"]
        valid_affiliation_identifier_types = ["ROR", "Other"]

        try: 
            self.check_required_fields(authors_df, columns_to_check)
        except Exception as e:
            raise ValueError(f"Validation error in check_required_fields: {str(e)}")
        try: 
            self.validate_affiliation_identifier(authors_df, valid_affiliation_identifier_types)
        except Exception as e:
            raise ValueError(f"Validation error in validate_affiliation_identifier: {str(e)}")
        try:
            self.validate_author_identifier(authors_df, valid_identifier_types)
        except Exception as e:
            raise ValueError(f"Validation error in validate_author_identifier: {str(e)}")        
    def validate_affiliation_identifier(self, authors_df, valid_affiliation_identifier_types):
        if 'author_affiliation_identifier' in authors_df.columns:
            authors_df['author_affiliation_identifier'] = authors_df['author_affiliation_identifier'].fillna('')
            authors_df['author_affiliation_identifier_type'] = authors_df['author_affiliation_identifier_type'].fillna('')

            # Find rows where author_affiliation_identifier is not empty and author_affiliation_identifier_type is empty
            missing_affil_type = authors_df[
                authors_df['author_affiliation_identifier'].apply(lambda x: not self.is_cell_empty(x)) & 
                authors_df['author_affiliation_identifier_type'].apply(lambda x: self.is_cell_empty(x))
            ]
            if not missing_affil_type.empty:
                raise ValueError("author_affiliation_identifier_type is required when author_affiliation_identifier is provided.")

            # Find rows where author_affiliation_identifier is not empty and author_affiliation_identifier_type is invalid
            invalid_affil_types = authors_df[
                authors_df['author_affiliation_identifier'].apply(lambda x: not self.is_cell_empty(x)) & 
                ~authors_df['author_affiliation_identifier_type'].isin(valid_affiliation_identifier_types)
            ]
            if not invalid_affil_types.empty:
                raise ValueError("Invalid author_affiliation_identifier_type. Must be one of: " + ", ".join(valid_affiliation_identifier_types))

            # Find rows where author_affiliation_identifier is not a valid URL
            invalid_entries = authors_df[
                authors_df['author_affiliation_identifier'].apply(lambda x: not self.is_cell_empty(x)) &
                authors_df['author_affiliation_identifier'].apply(lambda x: not self.is_url(str(x)))
            ]
            if not invalid_entries.empty:
                error_message = "Invalid URLs found at the following entries:\n"
                for idx, value in invalid_entries['author_affiliation_identifier'].items():
                    error_message += f"Index {idx}: {value}\n"
                raise ValueError(error_message)



            
    def validate_author_identifier(self, authors_df, valid_identifier_types):
        if 'author_identifier' in authors_df.columns:
            valid_identifiers = authors_df[~authors_df['author_identifier'].apply(self.is_cell_empty)]
            
            if not valid_identifiers.empty:
                missing_identifier_type = valid_identifiers[valid_identifiers['author_identifier_type'].apply(self.is_cell_empty)]
                if not missing_identifier_type.empty:
                    raise ValueError("author_identifier_type is required when author_identifier is provided.")

                invalid_identifier_types = valid_identifiers[~valid_identifiers['author_identifier_type'].isin(valid_identifier_types)]
                if not invalid_identifier_types.empty:
                    raise ValueError("author_identifier_type is invalid. must be one of: " + ", ".join(valid_identifier_types))



    def validate_related_resources(self, related_resources_df):
        required_fields = ['related_resource_type', 'related_resource_url', 'related_resource_title', 'relation_type']
        valid_resource_types = ["Audiovisual", "Book", "BookChapter", "Collection", "ComputationalNotebook", "ConferencePaper", "ConferenceProceeding", "DataPaper", "Dataset", "Dissertation", "Event", "Image", "Instrument", "InteractiveResource", "Journal", "JournalArticle", "Model", "Other", "OutputManagementPlan", "PeerReview", "PhysicalObject", "Preprint", "Report", "Service", "Software", "Sound", "Standard", "StudyRegistration", "Text", "Workflow"]

        valid_relation_types = [
            "IsCitedBy", "Cites", "IsSupplementTo", "IsSupplementedBy", "IsContinuedBy", "Continues","IsNewVersionOf", "IsPreviousVersionOf","IsPartOf","HasPart","IsPublishedIn","IsReferencedBy","References","IsDocumentedBy","Documents","IsCompiledBy","Compiles","IsVariantFormOf",    "IsOriginalFormOf","IsIdenticalTo","HasMetadata", "IsMetadataFor","Reviews","IsReviewedBy","IsDerivedFrom","IsSourceOf","Describes","IsDescribedBy","HasVersion","IsVersionOf","Requires","IsRequiredBy","Obsoletes","IsObsoletedBy","Collects","IsCollectedBy"
        ]
        
        # Check for any missing required fields in any of the related resources entries
        if related_resources_df[required_fields].map(self.is_cell_empty).any().any():
            raise ValueError("All related resource fields must be provided when a related resource is specified.")
        
        # make sure the related_resource_url is a valid URL
        invalid_entries = related_resources_df[related_resources_df['related_resource_url'].apply(lambda x: not self.is_url(str(x)))]
        if not invalid_entries.empty:
            error_message = "Invalid URLs found at the following entries:\n"
            for idx, value in invalid_entries['related_resource_url'].items():
                error_message += f"Index {idx}: {value}\n"
            raise ValueError(error_message)
        # Check if 'related_resource_type' is valid
        if not related_resources_df['related_resource_type'].isin(valid_resource_types).all():
            invalid_types = related_resources_df[~related_resources_df['related_resource_type'].isin(valid_resource_types)]['related_resource_type'].unique()
            raise ValueError(f"Invalid related_resource_type. Must be one of: {', '.join(valid_resource_types)}. Found invalid types: {', '.join(invalid_types)}")
        
        # Check if 'relation_type' is valid
        if not related_resources_df['relation_type'].isin(valid_relation_types).all():
            invalid_relations = related_resources_df[~related_resources_df['relation_type'].isin(valid_relation_types)]['relation_type'].unique()
            raise ValueError(f"Invalid relation_type. Must be one of: {', '.join(valid_relation_types)}. Found invalid types: {', '.join(invalid_relations)}")

    def validate_parent(self, samples_df):
        sample_numbers = samples_df["sample_number"].tolist()

        for index, row in samples_df.iterrows():
            parent = row["parent_sample"]
            if self.is_cell_empty(parent):
                continue
            # if pd.notna(parent) and parent not in sample_numbers:
            #     raise ValueError(f"Row {index}: parent_sample {parent} does not exist in sample_number column")

    
    def validate_epsg(self, samples_df):
        # List of valid EPSG codes
        valid_epsg_codes = [
            4202, 4203, 4283, 4326, 4347, 4348, 4938, 4939, 4979,
            7842, 7843, 7844, 9462, 9463, 9464
        ]
        
        # Identify rows with non-numeric latitude or longitude
        invalid_latitudes = samples_df['point_latitude'].apply(lambda x: not self.is_cell_empty(x) and not self.is_numeric(x))
        invalid_longitudes = samples_df['point_longitude'].apply(lambda x: not self.is_cell_empty(x) and not self.is_numeric(x))

        # Raise an error if any invalid rows are found
        if invalid_latitudes.any() or invalid_longitudes.any():
            error_message = "Invalid values found in point_latitude or point_longitude:\n"
            if invalid_latitudes.any():
                error_message += f"Invalid point_latitude values:\n{samples_df[invalid_latitudes]}\n"
            if invalid_longitudes.any():
                error_message += f"Invalid point_longitude values:\n{samples_df[invalid_longitudes]}\n"
            raise ValueError(error_message)
        
        # Check for missing EPSG when coordinates are provided
        missing_epsg = samples_df[
            (samples_df['point_latitude'].apply(lambda x: not self.is_cell_empty(x))) &
            (samples_df['point_longitude'].apply(lambda x: not self.is_cell_empty(x))) &
            (samples_df['epsg_code'].apply(self.is_cell_empty))
        ]
        if not missing_epsg.empty:
            raise ValueError("EPSG is required when both point_latitude and point_longitude are specified.")

        # Check for invalid EPSG codes
        invalid_epsg = samples_df[
            samples_df['epsg_code'].apply(lambda x: not self.is_cell_empty(x) and x not in valid_epsg_codes)
        ]
        if not invalid_epsg.empty:
            invalid_codes = invalid_epsg['epsg_code'].unique()
            raise ValueError(f"Invalid EPSG codes detected. Valid codes are: {', '.join(map(str, valid_epsg_codes))}. Found invalid codes: {', '.join(map(str, invalid_codes))}")
    def get_epsg_name(self, epsg_code):
        external_url = f'https://apps.epsg.org/api/v1/CoordRefSystem/?includeDeprecated=false&pageSize=50&page={0}&keywords={epsg_code}'
        response = requests.get(external_url)
        if response.ok:
            espg_data = json.loads(response.content.decode('utf-8'))
            return espg_data['Results'][0]['Name']
        else:
            return None
        
    def is_url(self, url: str) -> bool:
        """
        Check if the given string is a valid URL.

        Args:
        url (str): The URL to check.

        Returns:
        bool: True if the URL is valid, False otherwise.
        """
        # use re to check if the url is valid
        url_pattern = re.compile(
            r'^(?:http|ftp)s?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE
        )
        return bool(url_pattern.match(url))

    
    def is_numeric(self, value):
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False
    def is_cell_empty(self, cell):
        return pd.isna(cell) or (isinstance(cell, str) and cell.strip() == '')

    def set_parent_sample(self, context):
        """
        Sets the parent sample for each created sample.
        The 'parent_sample' field can be a DOI or a sample number.
        """
        preview_data = session.get('preview_data', {})
        samples = preview_data.get('samples', [])

        created_samples = session.get('created_samples', [])
        log = logging.getLogger(__name__)
        for sample in samples:
            log.info(f"set_parent_sample sample : {sample}")

            parent_sample = sample.get('parent_sample')
            if not parent_sample:
                continue

            log.info(f"set_parent_sample parent_sample : {parent_sample}")

            # Attempt to find the parent sample by DOI or sample number
            parent_package = self.find_parent_package(parent_sample, context, samples, created_samples)
            if not parent_package:
                continue

            log.info(f"parent_package : {parent_package}")

            # Update the sample with the parent sample ID
            sample_id = self.get_created_sample_id(sample)
            log.info(f"sample_id : {sample_id}")

            if 'id' not in parent_package:
                parent_package['id'] = self.get_created_sample_id(parent_package)

            log.info(f"parent_package['id'] : {parent_package['id']}")

            if sample_id and 'id' in parent_package:
                try:
                    existing_sample = toolkit.get_action('package_show')(context, {'id': sample_id})
                    existing_sample['parent'] = parent_package['id']
                    toolkit.get_action('package_update')(context, existing_sample)
                except Exception as e:
                    log.error(f"Failed to update sample {sample_id} with parent sample {parent_package['id']}: {e}")

    def find_parent_package(self, parent_sample, context, preview_samples, created_samples):
        """
        Finds the parent package based on DOI or sample number.
        """
        # Attempt to find by DOI
        try:
            package = toolkit.get_action('package_search')(context, {'q': f'doi:{parent_sample}'})
            if package['results']:
                return package['results'][0]
        except Exception as e:
            log.warning(f"Failed to find parent package by DOI {parent_sample}: {e}")

        # Attempt to find by sample number within preview_data
        for sample in preview_samples:
            if sample.get('sample_number') == parent_sample:
                # Check if the sample has been created and has an ID
                for created_sample in created_samples:
                    if created_sample['sample_number'] == sample.get('sample_number'):
                        return created_sample

        log.warning(f"Parent sample {parent_sample} not found by DOI or sample number.")
        return None

    def get_created_sample_id(self, preview_sample):
        """
        Finds the created sample ID corresponding to the preview sample.
        """
        created_samples = session.get('created_samples', [])
        for created_sample in created_samples:
            if created_sample['sample_number'] == preview_sample.get('sample_number'):
                return created_sample['id']
        return None


    
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
        update_option = request.form.get('update')
        preview_data = {}
        file_name = ''
        
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
                created_sample_ids = []
                successful_creations = 0
                unsuccessful_creations = 0

                for sample_data in data:
                    try:
                        created_sample = get_action('package_create')(context, sample_data)
                        created_sample_ids.append({
                            'id': created_sample['id'],
                            'sample_number': sample_data.get('sample_number')
                        })
                        successful_creations += 1
                        sample_data['status'] = "created"
                    except Exception as e:
                        error_message = str(e)
                        log.error(f"Failed to create sample: {error_message}")
                        unsuccessful_creations += 1
                        sample_data['status'] = "error"
                        sample_data['log'] = error_message

                        # Rollback: delete all successfully created samples
                        for sample in created_sample_ids:
                            try:
                                get_action('package_delete')(context, {'id': sample['id']})
                            except Exception as delete_exception:
                                # Log the exception, but continue with the rollback
                                log.error(f"Failed to delete sample {sample['id']}: {delete_exception}")
                        break

                for sample_data in data:
                    if 'status' not in sample_data:
                        sample_data['status'] = "error"
                    if 'type' not in sample_data:
                        sample_data['type'] = "NA"
                    if 'log' not in sample_data:
                        sample_data['log'] = ""

                if unsuccessful_creations == 0:
                    # Store the created samples in the session for later use
                    session['created_samples'] = created_sample_ids
                    # All samples were created successfully
                    self.set_parent_sample(context)
                    session.pop('preview_data', None)
                    session.pop('file_name', None)
                    session.pop('created_samples', None)
                    h.flash_success(_('Successfully processed your submission'))
                    return render_template('batch/new.html', group=org_id, preview_data={}, file_name='')
                
                elif successful_creations == 0:
                    h.flash_error(_('Failed to create any samples.'), 'error')
                    return render_template('batch/new.html', group=org_id, preview_data=preview_data, file_name=file_name)
                else:
                    h.flash_error(f"Successfully created {successful_creations} samples. {unsuccessful_creations} samples failed to create and have been rolled back.")
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

def convert_to_serializable(obj):
    """
    Recursively convert pandas objects to JSON-serializable formats.
    """
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient='records')
    elif isinstance(obj, pd.Series):
        return obj.to_dict()
    elif isinstance(obj, dict):
        return {k: convert_to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_serializable(i) for i in obj]
    else:
        return obj

@igsn_theme.route('/get_preview_data', methods=['GET'])
def get_preview_data():
    """
    Endpoint to fetch the preview data.
    """
    preview_data = session.get('preview_data', {})
    preview_data_serializable = convert_to_serializable(preview_data)
    return jsonify(preview_data_serializable)

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

    logger = logging.getLogger(__name__)

    try:
        if toolkit.request.method == 'POST':
            email_body = generate_new_collection_email_body(request)
            request.values = request.values.copy()
            request.values['content'] = email_body
            
                                                 
            if contact_plugin_available:
                result = _helpers.submit()
                if result.get('success', False):
                    try:
                        send_email_to_requester_new_col(request)
                    except Exception as email_error:
                        logger.error('An error occurred while sending the email to the requester: {}'.format(str(email_error)))

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
    logger = logging.getLogger(__name__)

    try: 
        if toolkit.request.method == 'POST':

            email_body = generate_join_collection_email_body(request, org_id,org_name)
            request.values = request.values.copy()
            request.values['content'] = email_body

            if contact_plugin_available:               
                result = _helpers.submit()
                if result.get('success', False):
                    try:
                        send_email_to_requester_join_col(request, org_id,org_name)
                    except Exception as email_error:
                        logger.error('An error occurred while sending the email to the requester: {}'.format(str(email_error)))
                    
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
        logger.error('An error occurred while processing your request: {}'.format(str(e)))
        return toolkit.abort(500, toolkit._('Internal server error'))
 

def send_email_to_requester_new_col(request):
    """
    Mail a confirmation to the user to create a new collection
    """
    collection_full_name= request.values.get('collection_full_name')
    recipient_email= request.values.get('email')
    recipient_name= request.values.get('name')
    body = generate_requester_new_email_body(request)
    subject = f'AuScope Sample Repository - Request to create collection "{collection_full_name}" has been submitted'
    mailer.mail_recipient(recipient_name, recipient_email, subject, body)


def send_email_to_requester_join_col(request,org_id,org_name):
    """
    Mail a confirmation to the user to join a collection
    """
    recipient_email= request.values.get('email')
    recipient_name= request.values.get('name')
    body = generate_requester_join_email_body(request,org_id,org_name)
    subject = f'AuScope Sample Repository - Request to join the collection has been submitted "{org_name}"'
    mailer.mail_recipient(recipient_name, recipient_email, subject, body)


def generate_new_collection_email_body(request):
    data = {
        'name': request.values.get('name'),
        'email': request.values.get('email'),
        'collection_full_name': request.values.get('collection_full_name'),
        'collection_short_name': request.values.get('collection_short_name'),
        'is_culturally_sensitive': request.values.get('is_culturally_sensitive'),
        'description': request.values.get('description')
    }    
    email_body_template = """
    Dear AuScope Sample Repository admin,

    A new collection request has been submitted. Below are the details of the request:

    Contact Name: {{ data.name }}
    Contact Email: {{ data.email }}
    
    Collection Details:
    - Full Name: {{ data.collection_full_name }}
    - Short Name: {{ data.collection_short_name }}
    - Culturally Sensitive: {{ data.is_culturally_sensitive}}
    
    Description of the Collection:
    {{ data.description }}

    Please take the necessary steps to process this request.

    Thank you.

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
    Dear AuScope Sample Repository admin,

    A new request to join the collection has been submitted. Below are the details of the request:

    Contact Name: {{ data.name }}
    Contact Email: {{ data.email }}

    Description of Request:
    {{ data.description }}

    Collection Details:
    - Collection ID: {{ data.collection_id }}
    - Collection Name: {{ data.collection_name }}

    Please take the necessary steps to process this request.

    Thank you.
    
    """
    return render_template_string(email_body_template, data=data)

def generate_requester_new_email_body(request):
    """
    Generates the email body for the requester.
    """
    data = {
        'name': request.values.get('name'),
        'email': request.values.get('email'),
        'collection_full_name': request.values.get('collection_full_name'),
        'collection_short_name': request.values.get('collection_short_name'),
        'is_culturally_sensitive': request.values.get('is_culturally_sensitive'),
        'description': request.values.get('description')
    }    
        
    site_title = config.get('ckan.site_title')
    site_url = config.get('ckan.site_url')
    return f"""
Dear {data['name']},

Thank you for submitting a new request to create a new collection. Below are the details of the request:

Contact Name: {data['name']}
Contact Email: {data['email']}

Collection Details:
- Full Name: {data['collection_full_name']}
- Short Name: {data['collection_short_name']}
- Culturally Sensitive: {data['is_culturally_sensitive']}

Description of the Collection:
{data['description']}

Our admin will review and contact you with regards to creating your collection.

Kind Regards,
AuScope Sample Repository
--
Message sent by {site_title} ({site_url})
    """

def generate_requester_join_email_body(request,org_id,org_name):
    """
    Generates the email body for the requester.
    """
    data = {
        'name': request.values.get('name'),
        'email': request.values.get('email'),
        'description': request.values.get('description'),
        'collection_id': org_id,
        'collection_name': org_name
    }
        
    site_title = config.get('ckan.site_title')
    site_url = config.get('ckan.site_url')
    return f"""
Dear {data['name']},

Thank you for submitting a new request to join the collection. Below are the details of the request:

Contact Name: {data['name']}
Contact Email: {data['email']}

Description of Request:
{data['description']}

Collection Details:
- Collection ID: { data['collection_id'] }
- Collection Name: { data['collection_name'] }

Our admin will review and contact you with regards to joining the collection.

Kind Regards,
AuScope Sample Repository
--
Message sent by {site_title} ({site_url})
    """


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

@igsn_theme.route('/api/proxy/fetch_terms', methods=['GET'])
def fetch_terms( ):
    page = request.args.get('page', 0)
    keywords = request.args.get('keywords', '')
    external_url = f'https://vocabs.ardc.edu.au/repository/api/lda/anzsrc-2020-for/concept.json?_page={page}&labelcontains={keywords}'

    response = requests.get(external_url)
    if response.ok:
        return Response(response.content, content_type=response.headers['Content-Type'], status=response.status_code)
    else:
        return {"error": "Failed to fetch terms"}, 502
    
@igsn_theme.route('/api/proxy/fetch_gcmd', methods=['GET'])
def fetch_gcmd():
    page = request.args.get('page', 0)
    keywords = request.args.get('keywords', '')
    external_url = f'https://vocabs.ardc.edu.au/repository/api/lda/ardc-curated/gcmd-sciencekeywords/17-5-2023-12-21/concept.json?_page={page}&labelcontains={keywords}'
   
    response = requests.get(external_url)   
    if response.ok:
        return Response(response.content, content_type=response.headers['Content-Type'], status=response.status_code)
    else:
        return {"error": "Failed to fetch gcmd"}, 502
    
def get_blueprints():
    return [igsn_theme]