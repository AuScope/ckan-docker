from flask import Blueprint, request, Response, render_template, redirect, url_for, flash
from flask.views import MethodView
from typing import Any
import requests
import os

from ckan.plugins.toolkit import get_action, h
from ckan.model import Package
from ckan.common import _, g, current_user
import ckan.lib.base as base
import ckan.logic as logic
import ckan.lib.helpers as helpers
from ckanext.igsn_theme.logic.action import process_excel, create_package
import logging

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
        org_id = request.args.get('group')
        return render_template('batch/new.html',group=org_id)
    
    def post(self):
        """
        Handles the POST request to upload and process the batch dataset file or submit a URL.
        """
        context = self._prepare()

        org_id = request.args.get('group')
        uploaded_file = request.files.get('file')

        if not org_id:
            h.flash_error(_('No collection is selected.'))
            return redirect(url_for('igsn_theme.batch_upload')) 

        if not uploaded_file :
            h.flash_error(_('No file provided.'))
            return redirect(url_for('igsn_theme.batch_upload', group=org_id))

        try:
            if uploaded_file:
                file_name = uploaded_file.filename
                file_extension = os.path.splitext(file_name)[1].lower()
                if file_extension not in ['.xlsx', '.xls']:
                    flash('Please upload an Excel file (.xlsx or .xls).', 'error')
                    return redirect(url_for('igsn_theme.batch_upload', group=org_id))  

                data = process_excel(uploaded_file, org_id)
                results = []

                for package_data in data:
                    package = create_package(context, package_data)
                    results.append(package)

                h.flash_success(_('Successfully processed your submission'))
                return redirect(url_for('igsn_theme.batch_upload', group=org_id))

        except NotAuthorized:
            base.abort(403, _('Unauthorized to read package'))
        except NotFound:
            base.abort(404, _('Not Found'))
        except ValidationError as e:
            h.flash_error(_('Validation error: ') + str(e))
            return redirect(url_for('igsn_theme.batch_upload', group=org_id))
        except Exception as e:
            h.flash_error(_('Unexpected error: ') + str(e))
            return redirect(url_for('igsn_theme.batch_upload', group=org_id))

        return redirect(url_for('igsn_theme.batch_upload', group=org_id))


def page():
    return "Hello, igsn_theme!"


igsn_theme.add_url_rule("/igsn_theme/page", view_func=page)


# def project_index():
#     return helpers.redirect_to(controller='group', action='index')

# def project_new():
#     return helpers.redirect_to(controller='group', action='new')

# def project_edit(id):
#     return helpers.redirect_to(controller='group', action='edit', id=id)

# def project_read(id):
#     return helpers.redirect_to(controller='group', action='read', id=id)

# igsn_theme.add_url_rule("/project", view_func=project_index)
# igsn_theme.add_url_rule("/new", view_func=project_new)
# igsn_theme.add_url_rule("/igsn_theme/edit/<id>", view_func=project_edit)
# igsn_theme.add_url_rule("/igsn_theme/<id>", view_func=project_read)


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



