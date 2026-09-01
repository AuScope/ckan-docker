from flask import session
import requests
from ckan.plugins.toolkit import get_action
import ckan.plugins.toolkit as toolkit
from datetime import date
import pandas as pd
import logging
import json
import os
import re
import tempfile
from ckanext.igsn_theme.logic.batch_validation import get_organization_name, is_numeric, is_cell_empty, is_url, validate_user_keywords, generate_sample_name, generate_sample_title
log = logging.getLogger(__name__)

# Directory used to persist background job state between the worker process and
# the web process.  We write a small JSON file per job so the status endpoint
# can read it without needing access to the RQ job object.
_JOB_STATE_DIR = os.path.join(tempfile.gettempdir(), 'ckan_batch_jobs')


_UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)


def _validate_job_id(job_id):
    """Raise ValueError if *job_id* is not a valid UUID string."""
    if not _UUID_RE.match(str(job_id)):
        raise ValueError(f"Invalid job_id: {job_id!r}")


def _job_state_path(job_id):
    """Return the filesystem path for the state file of *job_id*.

    Raises ``ValueError`` if *job_id* is not a valid UUID or if the resolved
    path would escape the job-state directory.
    """
    _validate_job_id(job_id)
    os.makedirs(_JOB_STATE_DIR, exist_ok=True)
    # job_id has been validated as UUID (hex + hyphens only); the re.sub is an
    # additional defence-in-depth step before building the filesystem path.
    safe_id = re.sub(r'[^A-Za-z0-9\-]', '', str(job_id))
    candidate = os.path.abspath(os.path.join(_JOB_STATE_DIR, f'batch_job_{safe_id}.json'))
    # Verify the resolved path is still inside _JOB_STATE_DIR (defence-in-depth).
    if not candidate.startswith(os.path.abspath(_JOB_STATE_DIR) + os.sep):
        raise ValueError(f"Computed job state path escapes the state directory: {candidate!r}")
    return candidate


def write_job_state(job_id, state):
    """Persist *state* dict to disk for *job_id* using an atomic write."""
    path = _job_state_path(job_id)
    tmp_path = path + '.tmp'
    with open(tmp_path, 'w') as fh:
        json.dump(state, fh)
    os.replace(tmp_path, path)


def read_job_state(job_id):
    """Read and return the state dict for *job_id*, or None if not found."""
    path = _job_state_path(job_id)
    try:
        with open(path, 'r') as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def batch_save_job(job_id, data, user_name, org_id):
    """
    Background job that creates CKAN packages for each sample in *data*.

    This function is designed to be enqueued via ``toolkit.enqueue_job`` and
    must not rely on the Flask request context or session.

    Args:
        job_id  (str): Identifier used to persist job state to disk.
        data    (list): List of sample data dicts (as produced by
                        ``prepare_samples_data``).
        user_name (str): CKAN username of the submitting user.
        org_id  (str): Organisation ID used when setting parent samples.
    """
    context = {
        'user': user_name,
        'ignore_auth': False,
    }

    log.info("batch_save_job started for job_id=%s, %d samples", job_id, len(data))
    write_job_state(job_id, {
        'status': 'running',
        'total': len(data),
        'processed': 0,
        'successful': 0,
        'unsuccessful': 0,
        'samples': [],
    })

    created_sample_ids = []
    successful_creations = 0
    unsuccessful_creations = 0

    for i, sample_data in enumerate(data):
        _error_occurred = False
        try:
            log.info("batch_save_job: creating sample %d/%d", i + 1, len(data))
            created_sample = get_action('package_create')(context, sample_data)
            created_sample_ids.append({
                'id': created_sample['id'],
                'sample_number': sample_data.get('sample_number'),
            })
            successful_creations += 1
            sample_data['status'] = 'created'
        except Exception as exc:
            error_message = str(exc)
            log.error("batch_save_job: failed to create sample: %s", error_message)
            unsuccessful_creations += 1
            sample_data['status'] = 'error'
            sample_data['log'] = error_message
            _error_occurred = True

            # Rollback: delete all successfully created samples
            for created in created_sample_ids:
                try:
                    get_action('package_delete')(context, {'id': created['id']})
                except Exception as del_exc:
                    log.error("batch_save_job: rollback delete failed for %s: %s", created['id'], del_exc)

        # Write incremental progress after every sample (success or failure)
        write_job_state(job_id, {
            'status': 'running',
            'total': len(data),
            'processed': i + 1,
            'successful': successful_creations,
            'unsuccessful': unsuccessful_creations,
            'samples': _serialisable_samples(data[:i + 1]),
        })

        if _error_occurred:
            break

    # Ensure any samples that were never reached have a status
    for sample_data in data:
        if 'status' not in sample_data:
            sample_data['status'] = 'error'
        if 'type' not in sample_data:
            sample_data['type'] = 'NA'
        if 'log' not in sample_data:
            sample_data['log'] = ''

    # Set parent-sample relationships for successfully created samples
    if unsuccessful_creations == 0:
        try:
            set_parent_sample_with_data(context, data, created_sample_ids)
        except Exception as exc:
            log.error("batch_save_job: set_parent_sample failed: %s", exc)

    final_status = 'complete' if unsuccessful_creations == 0 else 'failed'
    write_job_state(job_id, {
        'status': final_status,
        'total': len(data),
        'processed': len(data),
        'successful': successful_creations,
        'unsuccessful': unsuccessful_creations,
        'samples': _serialisable_samples(data),
    })
    log.info("batch_save_job finished for job_id=%s status=%s", job_id, final_status)


def _serialisable_samples(samples):
    """Return a JSON-serialisable copy of *samples* (strip non-serialisable values)."""
    result = []
    for s in samples:
        clean = {}
        for k, v in s.items():
            try:
                json.dumps(v)
                clean[k] = v
            except (TypeError, ValueError):
                clean[k] = str(v)
        result.append(clean)
    return result


def generate_location_geojson(coordinates_list):
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

def process_author_emails(sample, authors_df):
        author_emails = [email.strip() for email in sample.get("author_emails", "").split(";")]
        matched_authors = authors_df[authors_df["author_email"].isin(author_emails)]
        return json.dumps(matched_authors.to_dict("records"))

def prepare_samples_data(samples_df, authors_df, related_resources_df, funding_df, org_id):
        samples_data = []
        # Keep a dictionary to cache EPSG names to avoid repeated API calls for the same EPSG code
        current_epsg_dict = {}
        org = toolkit.get_action('organization_show')({}, {'id': org_id})
        org_contact_name = org.get('contact_name', 'test')
        org_contact_email = org.get('contact_email', '')
        # Get the organization name uses a costly API call, so we do it once and reuse it for all samples
        org_name = get_organization_name(org_id)
        for _, row in samples_df.iterrows():
            sample = row.to_dict()
            sample["author"] = process_author_emails(sample, authors_df)
            sample["related_resource"] = process_related_resources(sample, related_resources_df)
            sample["funder"] = process_funding_info(sample, funding_df)
            sample['user_keywords'] = validate_user_keywords(sample['user_keywords'])
            sample['publication_date'] = date.today().isoformat()
            sample['private']=False
            sample['notes'] = sample['description']
            sample['location_choice'] = 'noLocation'
            sample['parent_sample'] = sample['parent_sample']
            sample['parent'] = ''

            sample['acquisition_start_date'] = row['acquisition_start_date'].strftime('%Y-%m-%d') if pd.notnull(row['acquisition_start_date']) else None
            sample['acquisition_end_date'] = row['acquisition_end_date'].strftime('%Y-%m-%d') if pd.notnull(row['acquisition_end_date']) else None

            sample['owner_org'] = org_id
            sample['sample_repository_contact_name'] = org_contact_name
            sample['sample_repository_contact_email'] = org_contact_email
            
            if 'point_latitude' in sample and sample['point_latitude'] != '' and 'point_longitude' in sample and sample['point_longitude'] != '':
                if not is_numeric(sample['point_latitude']) or not is_numeric(sample['point_longitude']):
                    raise ValueError("Latitude and Longitude must be numeric.")
                sample['location_choice'] = 'point'
                coordinates = [(sample['point_latitude'], sample['point_longitude'])]
                sample['location_data'] = generate_location_geojson(coordinates)
            if sample['epsg_code'] not in current_epsg_dict:
                sample['epsg'] = get_epsg_name(sample['epsg_code'])
                current_epsg_dict[sample['epsg_code']] = sample['epsg']
            else:
                sample['epsg'] = current_epsg_dict[sample['epsg_code']]
            defaults = {
                "publisher_identifier_type": "ROR",
                "publisher_identifier": "https://ror.org/04s1m4564",
                "publisher": "AuScope",
                "resource_type": "PhysicalObject",
            }
            sample.update(defaults)
            
            sample["name"] = generate_sample_name(org_name, sample['sample_type'], str(sample['sample_number']))
            sample["title"] = generate_sample_title(org_name, sample['sample_type'], str(sample['sample_number']))
            samples_data.append(sample)
        return samples_data
    
def process_related_resources(sample, related_resources_df):
    related_resources_urls = sample.get("related_resources_urls")
    if is_cell_empty(related_resources_urls):
        return "[]"
    
    related_resource_urls = [url.strip() for url in related_resources_urls.split(";")]
    for url in related_resource_urls:
        is_url(url)  # Check if the URL is valid
        related_resources = related_resources_df[related_resources_df['related_resource_url'] == url]
        required_fields = ['related_resource_type', 'related_resource_url', 'related_resource_title', 'relation_type']
        if related_resources[required_fields].map(is_cell_empty).any().any():
            raise ValueError(f"Missing required fields for related resource URL: {url}")

    matched_resources = related_resources_df[related_resources_df["related_resource_url"].isin(related_resource_urls)]
    return json.dumps(matched_resources.to_dict("records"))

def process_funding_info(sample, funding_df):
    if not is_cell_empty(sample.get("project_ids")):
        project_ids = [project_id.strip() for project_id in sample.get("project_ids").split(";")]
        for project_id in project_ids:
            funding_info = funding_df[funding_df['project_identifier'] == project_id]
            if funding_info.empty:
                raise ValueError(f"Missing funding information for project ID: {project_id}")
            for _, row in funding_info.iterrows():
                if is_cell_empty(row["funder_name"]):
                    raise ValueError(f"Row for project ID {project_id} must include a funder_name")
                if not is_cell_empty(row["funder_identifier"]) and is_cell_empty(row["funder_identifier_type"]):
                    raise ValueError(f"Row for project ID {project_id} with funder_identifier must include funder_identifier_type")
                if not is_cell_empty(row["funder_name"]):
                    if is_cell_empty(row["project_name"]) or is_cell_empty(row["project_identifier"]) or is_cell_empty(row["project_identifier_type"]):
                        raise ValueError(f"Row for funder_name {row['funder_name']} must include project_name, project_identifier, and project_identifier_type")

        matched_funder = funding_df[funding_df["project_identifier"].isin(project_ids)]
        return json.dumps(matched_funder.to_dict("records"))

        # matched_funder_name = funding_df.loc[funding_df["project_identifier"].isin(project_ids), "funder_name"]
        # return matched_funder_name.tolist()
    return "[]"
def get_epsg_name(epsg_code):
        external_url = f'https://apps.epsg.org/api/v1/CoordRefSystem/?includeDeprecated=false&pageSize=50&page={0}&keywords={epsg_code}'
        response = requests.get(external_url)
        if response.ok:
            espg_data = json.loads(response.content.decode('utf-8'))
            return espg_data['Results'][0]['Name']
        else:
            return None
        
def set_parent_sample_with_data(context, samples, created_samples):
    """
    Sets the parent sample for each created sample.

    Unlike :func:`set_parent_sample` this version receives *samples* and
    *created_samples* as arguments so it can be used inside a background
    job where the Flask session is not available.

    Args:
        context (dict): CKAN context dict.
        samples (list): List of sample dicts (as returned by
                        ``prepare_samples_data``).
        created_samples (list): List of ``{'id': ..., 'sample_number': ...}``
                                dicts for successfully created packages.
    """
    for sample in samples:
        parent_sample = sample.get('parent_sample')
        if not parent_sample:
            continue

        parent_package = find_parent_package(parent_sample, context, samples, created_samples)
        if not parent_package:
            continue

        sample_id = _get_created_sample_id_from_list(sample, created_samples)

        if 'id' not in parent_package:
            parent_package['id'] = _get_created_sample_id_from_list(parent_package, created_samples)

        if sample_id and 'id' in parent_package:
            try:
                existing_sample = toolkit.get_action('package_show')(context, {'id': sample_id})
                existing_sample['parent'] = parent_package['id']
                toolkit.get_action('package_update')(context, existing_sample)
            except Exception as e:
                log.error(f"Failed to update sample {sample_id} with parent sample {parent_package['id']}: {e}")


def _get_created_sample_id_from_list(preview_sample, created_samples):
    """Return the CKAN package id for *preview_sample* from *created_samples*."""
    for created_sample in created_samples:
        if created_sample['sample_number'] == preview_sample.get('sample_number'):
            return created_sample['id']
    return None


def set_parent_sample(context):
        """
        Sets the parent sample for each created sample.
        The 'parent_sample' field can be a DOI or a sample number.
        """
        preview_data = session.get('preview_data', {})
        samples = preview_data.get('samples', [])

        created_samples = session.get('created_samples', [])
        log = logging.getLogger(__name__)
        for sample in samples:
            # log.info(f"set_parent_sample sample : {sample}")

            parent_sample = sample.get('parent_sample')
            if not parent_sample:
                continue

            # log.info(f"set_parent_sample parent_sample : {parent_sample}")

            # Attempt to find the parent sample by DOI or sample number
            parent_package = find_parent_package(parent_sample, context, samples, created_samples)
            if not parent_package:
                continue

            # log.info(f"parent_package : {parent_package}")

            # Update the sample with the parent sample ID
            sample_id = get_created_sample_id(sample)
            # log.info(f"sample_id : {sample_id}")

            if 'id' not in parent_package:
                parent_package['id'] = get_created_sample_id(parent_package)

            # log.info(f"parent_package['id'] : {parent_package['id']}")

            if sample_id and 'id' in parent_package:
                try:
                    existing_sample = toolkit.get_action('package_show')(context, {'id': sample_id})
                    existing_sample['parent'] = parent_package['id']
                    toolkit.get_action('package_update')(context, existing_sample)
                except Exception as e:
                    log.error(f"Failed to update sample {sample_id} with parent sample {parent_package['id']}: {e}")
                    
def find_parent_package(parent_sample, context, preview_samples, created_samples):
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

def get_created_sample_id(preview_sample):
    """
    Finds the created sample ID corresponding to the preview sample.
    """
    created_samples = session.get('created_samples', [])
    for created_sample in created_samples:
        if created_sample['sample_number'] == preview_sample.get('sample_number'):
            return created_sample['id']
    return None

def read_excel_sheets(excel_data, sheets):
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
