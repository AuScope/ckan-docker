from ckan.plugins import toolkit

def auscope_theme_hello():
    return "Hello, auscope_theme!"

def is_creating_dataset():
    """Determine if the user is creating or managing a dataset."""
    current_path = toolkit.request.path
    if current_path.startswith('/dataset/new'):
        return True
    return False

def get_helpers():
    return {
        "auscope_theme_hello": auscope_theme_hello,
        "is_creating_dataset" :is_creating_dataset
    }
