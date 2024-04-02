from flask import Blueprint, request, Response, render_template, redirect, url_for, flash
from flask.views import MethodView
from typing import Any
import requests

from ckan.plugins.toolkit import get_action, h
from ckan.model import Package
from ckan.common import _, g, current_user
import ckan.lib.base as base
import ckan.logic as logic
import ckan.lib.helpers as helpers

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

    def post(self):
        """
        Handles the POST request to upload and process the batch dataset file.
        """
        context = self._prepare()

        uploaded_file = request.files.get('file')
        if not uploaded_file:
            h.flash_error(_('No file uploaded.'))
            return redirect(url_for('igsn_theme.batch_upload'))

        try:
            # Add logic to process the uploaded file here

            h.flash_success(_('File successfully uploaded and processed'))
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



