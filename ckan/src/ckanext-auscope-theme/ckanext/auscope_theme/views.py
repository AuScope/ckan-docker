from flask import Blueprint, request, Response, render_template
import requests


auscope_theme = Blueprint(
    "auscope_theme", __name__)


def page():
    return "Hello, auscope_theme!"


# Add the proxy route
@auscope_theme.route('/api/proxy/fetch_terms', methods=['GET'])
def fetch_terms():
    page = request.args.get('page', 0)
    keywords = request.args.get('keywords', '')
    external_url = f'https://vocabs.ardc.edu.au/repository/api/lda/anzsrc-2020-for/concept.json?_page={page}&labelcontains={keywords}'

    response = requests.get(external_url)
    if response.ok:
        return Response(response.content, content_type=response.headers['Content-Type'], status=response.status_code)
    else:
        return {"error": "Failed to fetch terms"}, 502

@auscope_theme.route('/api/proxy/fetch_gcmd', methods=['GET'])
def fetch_gcmd():
    page = request.args.get('page', 0)
    keywords = request.args.get('keywords', '')
    external_url = f'https://vocabs.ardc.edu.au/repository/api/lda/ardc-curated/gcmd-sciencekeywords/17-5-2023-12-21/concept.json?_page={page}&labelcontains={keywords}'
   
    response = requests.get(external_url)   
    if response.ok:
        return Response(response.content, content_type=response.headers['Content-Type'], status=response.status_code)
    else:
        return {"error": "Failed to fetch gcmd"}, 502
      
@auscope_theme.route('/api/proxy/fetch_epsg', methods=['GET'])
def fetch_epsg():
    page = request.args.get('page', 0)
    keywords = request.args.get('keywords', '')
    external_url = f'https://apps.epsg.org/api/v1/CoordRefSystem/?includeDeprecated=false&pageSize=50&page={page}&keywords={keywords}'

    response = requests.get(external_url)
    if response.ok:
        return Response(response.content, content_type=response.headers['Content-Type'], status=response.status_code)
    else:
        return {"error": "Failed to fetch EPSG codes"}, 502

@auscope_theme.route('/declaration', methods=['GET'])
def declaration():
    return render_template('declaration/declaration.html')


def get_blueprints():
    return [auscope_theme]
