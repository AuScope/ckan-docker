from flask import Blueprint, Response
import requests

igsn_theme = Blueprint(
    "igsn_theme", __name__)


def page():
    return "Hello, igsn_theme!"


igsn_theme.add_url_rule(
    "/igsn_theme/page", view_func=page)



# Add the proxy route
@igsn_theme.route('/api/proxy/fetch_terms', methods=['GET'])
def fetch_terms():
    external_url = 'https://vocabs.ardc.edu.au/repository/api/lda/anzsrc-2020-for/concept.json' 
    response = requests.get(external_url)
    if response.ok:
        return Response(response.content, content_type=response.headers['Content-Type'], status=response.status_code)
    else:
        return {"error": "Failed to fetch terms"}, 502

@igsn_theme.route('/api/proxy/fetch_gcmd', methods=['GET'])
def fetch_gcmd():
    external_url = 'https://vocabs.ardc.edu.au/repository/api/lda/ardc-curated/gcmd-sciencekeywords/17-5-2023-12-21/concept.json' 
    response = requests.get(external_url)
    if response.ok:
        return Response(response.content, content_type=response.headers['Content-Type'], status=response.status_code)
    else:
        return {"error": "Failed to fetch gcmd"}, 502
    
@igsn_theme.route('/api/proxy/fetch_locality', methods=['GET'])
def fetch_locality():
    external_url = 'https://placenames.fsdf.org.au/' 
    response = requests.get(external_url)
    if response.ok:
        return Response(response.content, content_type=response.headers['Content-Type'], status=response.status_code)
    else:
        return {"error": "Failed to fetch locality"}, 502    
    
@igsn_theme.route('/api/proxy/fetch_epsg', methods=['GET'])
def fetch_epsg():
    external_url = 'https://apps.epsg.org/api/v1/CoordRefSystem'  
    response = requests.get(external_url)
    if response.ok:
        return Response(response.content, content_type=response.headers['Content-Type'], status=response.status_code)
    else:
        return {"error": "Failed to fetch EPSG codes"}, 502
        
igsn_theme.add_url_rule(
    "/igsn_theme/page", view_func=page)


def get_blueprints():
    return [igsn_theme]
