from flask import Blueprint, redirect, request, Response, render_template, redirect, url_for, session, jsonify
from flask.views import MethodView
import requests
from ckan.plugins import toolkit
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
import uuid as _uuid
from ckanext.igsn_theme.logic.batch_validation import validate_parent_samples, validate_related_resources, validate_authors, validate_samples, validate_sample_names
from ckanext.igsn_theme.logic.batch_process import (
    prepare_samples_data, read_excel_sheets,
    batch_save_job, read_job_state, write_job_state,
)
from ckanext.igsn_theme.logic import (
    email_notifications
)
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
    pre_errors = []
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
            all_errors = []
            content = uploaded_file.read()
            excel_data = BytesIO(content)
            sheets = ["samples", "authors", "related_resources", "funding"]
            dfs = read_excel_sheets(excel_data, sheets)
            
            samples_df = dfs["samples"]
            authors_df = dfs["authors"]
            related_resources_df = dfs["related_resources"]
            funding_df = dfs["funding"]
            
            all_errors.extend(validate_samples(samples_df, related_resources_df, authors_df, funding_df))
            all_errors.extend(validate_authors(authors_df))
            if len(related_resources_df) > 0:
                all_errors.extend(validate_related_resources(related_resources_df))
            all_errors.extend(validate_parent_samples(samples_df))
            all_errors.extend(validate_sample_names(samples_df, org_id))
            if all_errors:
                error_list = "\n".join(f"Error {i+1}. {error}. " for i, error in enumerate(all_errors))
                # format the error list to be displayed in human readable format
                formatted_errors = f"<pre style='white-space: pre-wrap;'>{error_list}</pre>"
                raise ValueError(f"""<pre>The following errors were found. Note The row number starts from 0.</pre> :
                    {formatted_errors}""")
                
            samples_data = prepare_samples_data(samples_df, authors_df, related_resources_df, funding_df, org_id)
            return_value = {
                "samples": samples_data,
                "authors": authors_df.to_dict("records"),
                "related_resources": related_resources_df.to_dict("records"),
                "funders": funding_df.to_dict("records")

            }
            return return_value

        except Exception as e:
            raise ValueError(f"{str(e)}")
        
    def get(self):
        """
        Handles the GET request to show the batch upload form.
        """
        self._prepare()
        org_id = request.args.get('group')
        return render_template('batch/new.html', group=org_id, preview_data={}, file_name="")

    def save_data(self, data, context):
        """
        Saves the data to CKAN by creating packages for each sample.

        Args:
        data (list): List of sample data dictionaries to be saved.
        context (dict): The CKAN context for authorization. 

        Returns:
        tuple: A tuple containing:
            - created_sample_ids (list): List of dictionaries with 'id' and 'sample_number' for each successfully created sample.
            - successful_creations (int): Count of successfully created samples.
            - unsuccessful_creations (int): Count of unsuccessfully created samples.
        """
        log.info(f"Starting to save data for {len(data)} samples.")
        log.info(f"Context: {context}")
        created_sample_ids = []
        successful_creations = 0
        unsuccessful_creations = 0
        for sample_data in data:
            try:
                log.info(f"Attempting to create sample with data: {sample_data}")
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
        return created_sample_ids, successful_creations, unsuccessful_creations
    
    def post(self):
        """
        Handles the POST request to upload and process the batch dataset file or submit a URL.
        """
        context = self._prepare()
        org_id = request.args.get('group')
        uploaded_file = request.files.get('file')
        save_option = request.form.get('save')
        preview_option = request.form.get('preview')
        #update_option = request.form.get('update')
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
                if not preview_data or not preview_data.get('samples') or not isinstance(preview_data['samples'], list):
                    h.flash_error(_('Please generate a preview first.'), 'error')
                    return redirect(url_for('igsn_theme.batch_upload', group=org_id))
                log.info(f"First 2 of preview data retrieved from session for saving: {preview_data['samples'][:2]}")
                log.info(f"{len(preview_data['samples'])=}")
                log.info(f"File name retrieved from session for saving: {file_name}")

                data = preview_data['samples']

                # Generate a stable job ID before enqueuing so it can be
                # threaded through both the state file and the worker function.
                job_id = str(_uuid.uuid4())

                # Seed the state file immediately so the status endpoint has
                # something to return before the worker picks up the job.
                write_job_state(job_id, {
                    'status': 'queued',
                    'total': len(data),
                    'processed': 0,
                    'successful': 0,
                    'unsuccessful': 0,
                    'samples': [],
                })

                # Enqueue the save operation as a background job so it does
                # not block the web request.
                log.info(f"Enqueuing batch save job with custom job ID: {job_id} for organization: {org_id} by user: {current_user.name}")
                #batch_save_job(job_id, data, current_user.name, org_id)
                rq_job =toolkit.enqueue_job(
                    batch_save_job,
                    [job_id, data, current_user.name, org_id],
                    title=f'Batch upload for Org# {org_id} by {current_user.name}',
                )
                queue_job_id = getattr(rq_job, "id", None)
                log.info(f"Enqueued batch save job with RQ job ID: {queue_job_id} and custom job ID: {job_id}")

                # Clear the preview from the session – the worker has its own
                # copy of the data passed as arguments.
                session.pop('preview_data', None)
                session.pop('file_name', None)

                return redirect(toolkit.config["ckan.site_url"].rstrip("/") + url_for(
                    'igsn_theme.batch_job_status_page',
                    job_id=job_id,
                    group=org_id
                ))

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
            import traceback
            log.error('Unexpected error uploading batch sample: ' + traceback.format_exc())
            h.flash_error(_('Unexpected error, see container log for more detail: ') + str(e), 'error')
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

@igsn_theme.route('/batch_job/<job_id>', methods=['GET'])
def batch_job_status_page(job_id):
    """
    Render the batch-upload job status/result page.

    The page polls ``/batch_job_status/<job_id>`` via JavaScript and updates
    itself until the job reaches a terminal state (``complete`` or ``failed``).
    """
    context = {
        'user': current_user.name,
        'auth_user_obj': current_user,
    }
    try:
        check_access('package_create', context)
    except NotAuthorized:
        base.abort(403, _('Unauthorized'))

    org_id = request.args.get('group', '')
    try:
        state = read_job_state(job_id) or {'status': 'unknown'}
    except ValueError:
        base.abort(404, _('Job not found'))
    return render_template(
        'batch/job_status.html',
        job_id=job_id,
        group=org_id,
        state=state,
    )


@igsn_theme.route('/batch_job_status/<job_id>', methods=['GET'])
def batch_job_status_api(job_id):
    """
    JSON endpoint to poll the status of a background batch-upload job.

    Returns a JSON object with at minimum the keys:
    ``status``        – one of ``queued``, ``running``, ``complete``, ``failed``, ``unknown``
    ``total``         – total number of samples in the job
    ``processed``     – number processed so far
    ``successful``    – successfully created packages
    ``unsuccessful``  – failed packages
    ``samples``       – list of per-sample dicts (status/log fields populated)
    """
    context = {
        'user': current_user.name,
        'auth_user_obj': current_user,
    }
    try:
        check_access('package_create', context)
    except NotAuthorized:
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        state = read_job_state(job_id)
    except ValueError:
        return jsonify({'error': 'Invalid job_id'}), 400
    if state is None:
        return jsonify({'status': 'unknown', 'total': 0, 'processed': 0,
                        'successful': 0, 'unsuccessful': 0, 'samples': []})
    return jsonify(state)

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
            email_body = email_notifications.generate_new_collection_admin_email_body(request)
            request.values = request.values.copy()
            request.values['content'] = email_body
            
            if contact_plugin_available:
                result = _helpers.submit()
                if result.get('success', False):
                    try:
                        email_notifications.send_new_collection_requester_confirmation_email(request)
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
    organization = get_action('organization_show')({}, {'id': org_id})
    org_name = organization['name']

    extra_vars = {
        'data': {},
        'errors': {},
        'error_summary': {},
    }
    logger = logging.getLogger(__name__)

    try: 
        if toolkit.request.method == 'POST':

            email_body = email_notifications.generate_join_collection_admin_email_body(request, org_id,org_name)
            request.values = request.values.copy()
            request.values['content'] = email_body

            if contact_plugin_available:               
                result = _helpers.submit()
                if result.get('success', False):
                    try:
                        email_notifications.send_join_collection_requester_confirmation_email(request, organization)
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

def make_tools_blueprint():
    bp = Blueprint('auscope_tools', __name__)

    @bp.route('/tools')
    def external():
        url = toolkit.config.get('auscope.tools_url', 'https://avre.auscope.org.au')
        return redirect(url, code=301)

    return bp
    
def get_blueprints():
    blueprints = [igsn_theme]
    blueprints.append(make_tools_blueprint())
    return blueprints
