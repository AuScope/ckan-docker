                # Clear the preview from the session – the worker has its own
                # copy of the data passed as arguments.
                session.pop('preview_data', None)
                session.pop('file_name', None)

                return redirect(url_for(
                    'igsn_theme.batch_job_status_page',
                    job_id=job_id,
                    group=org_id,
                    _external=True,
                    _scheme=request.scheme,
                    _host=request.host,
                ))
