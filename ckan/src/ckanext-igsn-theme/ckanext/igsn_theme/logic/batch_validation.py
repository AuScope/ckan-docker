import ckan.plugins.toolkit as toolkit
import re
import pandas as pd

# TODO this function also has some issues, when its empty: still return Invalid rows (depth_from >= depth_to): 0
def validate_sample_depth(sample_df):
    errors = []

    filtered_df = sample_df.dropna(subset=["depth_from", "depth_to"])

    # Convert 'depth_from' and 'depth_to' to numeric, treating them as strings initially
    filtered_df["depth_from"] = pd.to_numeric(filtered_df["depth_from"], errors="coerce")
    filtered_df["depth_to"] = pd.to_numeric(filtered_df["depth_to"], errors="coerce")

    # Remove rows where conversion to numeric failed
    filtered_df = filtered_df.dropna(subset=["depth_from", "depth_to"])

    # Compare depth_from and depth_to
    valid_mask = filtered_df["depth_from"] < filtered_df["depth_to"]
    invalid_df = filtered_df[~valid_mask]

    for index, row in invalid_df.iterrows():
        errors.append(f"Row {index}: Depth from {row['depth_from']} to {row['depth_to']} is invalid")
    return errors

def validate_elevation(sample_df):
    errors = []
    # Filter out empty cells
    non_empty_elevations = sample_df["elevation"].dropna().replace('', pd.NA).dropna()

    # Attempt to convert non-empty values to numeric
    numeric_result = pd.to_numeric(non_empty_elevations, errors='coerce')
    # Identify rows where conversion failed (resulting in NaN)
    invalid_rows = numeric_result[numeric_result.isna()]

    for index, value in invalid_rows.items():
        original_value = sample_df.loc[index, "elevation"]
        errors.append(f"Row {index}: Elevation '{original_value}' is not a valid number")
    return errors
    

def validate_match_related_resource_url(sample_df, resource_df):
    errors = []
    sample_urls = set()
    for cell in sample_df['related_resources_urls']:
        urls = set(url.strip() for url in cell.split(';') if url.strip())
        sample_urls.update(urls)
    # Check each URL in resource_df against the set of sample URLs
    missing_urls = []
    for url in resource_df['related_resource_url']:
        if url not in sample_urls:
            missing_urls.append(url)

    # If there are any missing URLs, raise an error
    if missing_urls:
        errors.append("The following related resource URLs are not in the sample sheet, please double check your related resource URLs:\n" + ', '.join(missing_urls))
    return errors
    
def validate_match_user_email(sample_df, author_df):
    errors = []
    sample_emails = set()
    for cell in sample_df['author_emails']:
        emails = set(email.strip() for email in cell.split(';') if email.strip())
        sample_emails.update(emails)
    # Check each email in author_df against the set of sample emails
    missing_emails = []
    for email in author_df['author_email']:
        if email not in sample_emails:
            missing_emails.append(email)

    # If there are any missing emails, raise an error
    if missing_emails:
        errors.append("The following author emails are not in the sample sheet, please double check your author emails:\n" + ', '.join(missing_emails))
    return errors

def validate_match_project_identifier(sample_df, project_df):
    errors = []
    sample_project_identifiers = set()
    for cell in sample_df['project_ids']:
        # Skip if the cell is empty or NaN
        if pd.isna(cell) or cell == '':
            continue
        project_identifiers = set(project_identifier.strip() for project_identifier in cell.split(';') if project_identifier.strip())
        sample_project_identifiers.update(project_identifiers)
    # Check each project identifier in project_df against the set of sample project identifiers
    missing_project_identifiers = []
    for project_identifier in project_df['project_identifier']:
        if project_identifier not in sample_project_identifiers and project_identifier != '':
            missing_project_identifiers.append(project_identifier)

    # If there are any missing project identifiers, raise an error
    if missing_project_identifiers:
        errors.append("The following project identifiers are not in the sample sheet, please double check your project identifiers:\n" + ', '.join(missing_project_identifiers))
    return errors

def validate_acquisition_date(sample_df):
    errors = []
    # Convert to datetime, coerce errors to NaT
    sample_df['acquisition_start_date'] = pd.to_datetime(sample_df['acquisition_start_date'], errors='coerce')
    sample_df['acquisition_end_date'] = pd.to_datetime(sample_df['acquisition_end_date'], errors='coerce')
    
    # Filter for rows where both dates are not null
    valid_df = sample_df.dropna(subset=['acquisition_start_date', 'acquisition_end_date'])
    
    # Compare dates only for non-null pairs
    invalid_mask = valid_df["acquisition_start_date"] >= valid_df["acquisition_end_date"]
    invalid_df = valid_df[invalid_mask]
    
    for index, row in invalid_df.iterrows():
        errors.append(f"Row {index}: acquisition_start_date {row['acquisition_start_date']} is not before acquisition_end_date {row['acquisition_end_date']}")
    return errors
    
def validate_parent_samples(df):
    errors = []
    
    # Convert date columns to datetime
    df['acquisition_start_date'] = pd.to_datetime(df['acquisition_start_date'])
    df['acquisition_end_date'] = pd.to_datetime(df['acquisition_end_date'])
    
    # Create a dictionary of samples in the current DataFrame
    current_samples = dict(zip(df['sample_number'], df['acquisition_start_date']))
    
    # Get list of all packages in CKAN
    try:
        package_list = toolkit.get_action('package_list')({}, {})
        ckan_samples = {}
        collection_sample_numbers = []
        for package in package_list:
            package_data = toolkit.get_action('package_show')({}, {'id': package})
            sample_number = package_data.get('sample_number')
            if sample_number:
                ckan_samples[sample_number] = pd.to_datetime(package_data.get('acquisition_start_date'))
                collection_sample_numbers.append(sample_number)
    except Exception as e:
        errors.append(f"Error fetching CKAN data: {str(e)}")
        raise ValueError("\n".join(errors))

    def validate_sample(row):
        if pd.isnull(row['parent_sample']) or row['parent_sample'] == '':
            return True

        if row['parent_sample'] == row['sample_number']:
            errors.append(f"Sample {row['sample_number']} references itself as parent")
            return False

        parent_start_date = None
        if row['parent_sample'] in current_samples:
            parent_start_date = current_samples[row['parent_sample']]
        elif row['parent_sample'] in ckan_samples:
            parent_start_date = ckan_samples[row['parent_sample']]
        else:
            errors.append(f"Parent sample {row['parent_sample']} for sample {row['sample_number']} not found in DataFrame or CKAN")
            return False

        if pd.isnull(parent_start_date):
            return True

        if row['acquisition_start_date'] < parent_start_date:
            errors.append(f"Sample {row['sample_number']} : {row['acquisition_start_date']} start date is earlier than its parent {row['parent_sample']} : {parent_start_date}")
            return False

        return True

    df['valid_parent'] = df.apply(validate_sample, axis=1)

    # Additional validation from validate_parent function
    sample_numbers = df["sample_number"].tolist()
    for index, row in df.iterrows():
        parent = row["parent_sample"]
        if pd.isna(parent) or parent == '':
            continue
        if parent not in sample_numbers and parent not in collection_sample_numbers:
            errors.append(f"Parent sample '{parent}' not found in the uploaded samples or the collection.")

    return errors

def check_required_fields(df, columns_to_check):
    errors = []
    empty_check = df[columns_to_check].isna() | (df[columns_to_check] == '')
    missing_fields = {}

    for col in columns_to_check:
        missing_in_col = empty_check[col]
        if missing_in_col.any():
            missing_fields[col] = df[missing_in_col].index.tolist()

    if missing_fields:
        for col, indexes in missing_fields.items():
            errors.append(f"Missing values in column '{col}': rows {indexes}")
    return errors

def check_unique_sample_number(samples_df):
    errors = []
    duplicates = samples_df[samples_df['sample_number'].duplicated(keep=False)]
    if not duplicates.empty:
        duplicate_values = duplicates['sample_number'].value_counts()
        errors.append(f"Duplicate sample numbers detected: {duplicate_values.index.tolist()}")
    return errors
    
def validate_epsg(samples_df):
    errors = []
    # List of valid EPSG codes
    valid_epsg_codes = [
        4202, 4203, 4283, 4326, 4347, 4348, 4938, 4939, 4979,
        7842, 7843, 7844, 9462, 9463, 9464
    ]
    
    # Identify rows with non-numeric latitude or longitude
    invalid_latitudes = samples_df['point_latitude'].apply(lambda x: not is_cell_empty(x) and not is_numeric(x))
    invalid_longitudes = samples_df['point_longitude'].apply(lambda x: not is_cell_empty(x) and not is_numeric(x))

    # Raise an error if any invalid rows are found
    if invalid_latitudes.any():
        errors.append(f"Invalid point_latitude values:\n{samples_df[invalid_latitudes]}")
    if invalid_longitudes.any():
        errors.append(f"Invalid point_longitude values:\n{samples_df[invalid_longitudes]}")
    
    
    # Check for missing EPSG when coordinates are provided
    missing_epsg = samples_df[
        (samples_df['point_latitude'].apply(lambda x: not is_cell_empty(x))) &
        (samples_df['point_longitude'].apply(lambda x: not is_cell_empty(x))) &
        (samples_df['epsg_code'].apply(is_cell_empty))
    ]
    if not missing_epsg.empty:
        errors.append("EPSG is required when both point_latitude and point_longitude are specified.")

    invalid_epsg = samples_df[
        samples_df['epsg_code'].apply(lambda x: not is_cell_empty(x) and x not in valid_epsg_codes)
    ]
    if not invalid_epsg.empty:
        invalid_codes = invalid_epsg['epsg_code'].unique()
        errors.append(f"Invalid EPSG codes detected. Valid codes are: {', '.join(map(str, valid_epsg_codes))}. Found invalid codes: {', '.join(map(str, invalid_codes))}")
    return errors

def is_cell_empty(cell):
    return pd.isna(cell) or (isinstance(cell, str) and cell.strip() == '')
def is_numeric(value):
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False
    
def is_url(url: str) -> bool:
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

def validate_affiliation_identifier(authors_df, valid_affiliation_identifier_types):
    errors = []
    if 'author_affiliation_identifier' in authors_df.columns:
        authors_df['author_affiliation_identifier'] = authors_df['author_affiliation_identifier'].fillna('')
        authors_df['author_affiliation_identifier_type'] = authors_df['author_affiliation_identifier_type'].fillna('')

        missing_affil_type = authors_df[
            authors_df['author_affiliation_identifier'].apply(lambda x: not is_cell_empty(x)) & 
            authors_df['author_affiliation_identifier_type'].apply(lambda x: is_cell_empty(x))
        ]
        if not missing_affil_type.empty:
            errors.append("author_affiliation_identifier_type is required when author_affiliation_identifier is provided.")

        invalid_affil_types = authors_df[
            authors_df['author_affiliation_identifier'].apply(lambda x: not is_cell_empty(x)) & 
            ~authors_df['author_affiliation_identifier_type'].isin(valid_affiliation_identifier_types)
        ]
        if not invalid_affil_types.empty:
            errors.append("Invalid author_affiliation_identifier_type. Must be one of: " + ", ".join(valid_affiliation_identifier_types))

        invalid_entries = authors_df[
            authors_df['author_affiliation_identifier'].apply(lambda x: not is_cell_empty(x)) &
            authors_df['author_affiliation_identifier'].apply(lambda x: not is_url(str(x)))
        ]
        if not invalid_entries.empty:
            error_message = "Invalid URLs found at the following entries:\n"
            for idx, value in invalid_entries['author_affiliation_identifier'].items():
                error_message += f"Index {idx}: {value}\n"
            errors.append(error_message)
    return errors

def validate_related_resources(related_resources_df):
    errors = []
    required_fields = ['related_resource_type', 'related_resource_url', 'related_resource_title', 'relation_type']
    valid_resource_types = ["Audiovisual", "Book", "BookChapter", "Collection", "ComputationalNotebook", "ConferencePaper", "ConferenceProceeding", "DataPaper", "Dataset", "Dissertation", "Event", "Image", "Instrument", "InteractiveResource", "Journal", "JournalArticle", "Model", "Other", "OutputManagementPlan", "PeerReview", "PhysicalObject", "Preprint", "Report", "Service", "Software", "Sound", "Standard", "StudyRegistration", "Text", "Workflow"]

    valid_relation_types = [
        "IsCitedBy", "Cites", "IsSupplementTo", "IsSupplementedBy", "IsContinuedBy", "Continues","IsNewVersionOf", "IsPreviousVersionOf","IsPartOf","HasPart","IsPublishedIn","IsReferencedBy","References","IsDocumentedBy","Documents","IsCompiledBy","Compiles","IsVariantFormOf",    "IsOriginalFormOf","IsIdenticalTo","HasMetadata", "IsMetadataFor","Reviews","IsReviewedBy","IsDerivedFrom","IsSourceOf","Describes","IsDescribedBy","HasVersion","IsVersionOf","Requires","IsRequiredBy","Obsoletes","IsObsoletedBy","Collects","IsCollectedBy"
    ]
    
    # Check for any missing required fields in any of the related resources entries
    if related_resources_df[required_fields].map(is_cell_empty).any().any():
        errors.append("Missing required fields in related resources entries.")
    
    # make sure the related_resource_url is a valid URL
    invalid_entries = related_resources_df[related_resources_df['related_resource_url'].apply(lambda x: not is_url(str(x)))]
    if not invalid_entries.empty:
        error_message = "Invalid URLs found at the following entries:\n"
        for idx, value in invalid_entries['related_resource_url'].items():
            error_message += f"Index {idx}: {value}\n"
        errors.append(error_message)

    if not related_resources_df['related_resource_type'].isin(valid_resource_types).all():
        invalid_types = related_resources_df[~related_resources_df['related_resource_type'].isin(valid_resource_types)]['related_resource_type'].unique()
        errors.append(f"Invalid related_resource_type. Must be one of: {', '.join(valid_resource_types)}. Found invalid types: {', '.join(invalid_types)}")
    
    if not related_resources_df['relation_type'].isin(valid_relation_types).all():
        invalid_relations = related_resources_df[~related_resources_df['relation_type'].isin(valid_relation_types)]['relation_type'].unique()
        errors.append(f"Invalid relation_type. Must be one of: {', '.join(valid_relation_types)}. Found invalid types: {', '.join(invalid_relations)}")

    return errors

def validate_author_identifier(authors_df, valid_identifier_types):
    errors = []
    if 'author_identifier' in authors_df.columns:
        valid_identifiers = authors_df[~authors_df['author_identifier'].apply(is_cell_empty)]
            
        if not valid_identifiers.empty:
            missing_identifier_type = valid_identifiers[valid_identifiers['author_identifier_type'].apply(is_cell_empty)]
            if not missing_identifier_type.empty:
                errors.append("author_identifier_type is required when author_identifier is provided for the following rows:")
                errors.extend(missing_identifier_type.index.tolist())

            invalid_identifier_types = valid_identifiers[~valid_identifiers['author_identifier_type'].isin(valid_identifier_types)]
            if not invalid_identifier_types.empty:
                errors.append(f"author_identifier_type is invalid. Must be one of: {', '.join(valid_identifier_types)}. Invalid types found in rows:")
                errors.append(invalid_identifier_types.index.tolist())
        # make sure the author_identifier is a valid URL
        invalid_url = valid_identifiers[~valid_identifiers['author_identifier'].apply(is_url)]
        if not invalid_url.empty:
            errors.append("Invalid URLs found in the following rows:")
            errors.append(invalid_url.index.tolist())
    return errors
def validate_sample_type(sample_df):
    errors = []
    sample_types = [
        "AC Chips", "Core", "Core - Friable", "Core Catcher", "Core Half Round",
        "Core Piece", "Core Quarter Round", "Core Section", "Core Section Half",
        "Core Slab", "Core Sub-Piece", "Core U-Channel", "Experimental", "Full Core",
        "Grab", "Heavy Mineral Concentrate", "Individual Sample", "Litter", "Other",
        "Phyllos", "RC Chips", "Rock Powder", "Soil Profile", "Soil", "Surface Soil",
        "Termite Mound", "Vegetation", "Water", "Pisolite", "Hardpan soil",
        "Thin Section", "Polished Block", "Polished Round"
    ]
    invalid_types = sample_df[~sample_df['sample_type'].isin(sample_types)]
    if not invalid_types.empty:
        errors.append(f"Invalid sample types found: {invalid_types['sample_type'].unique().tolist()}. Must be one of: {', '.join(sample_types)}")
    return errors

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
def validate_authors(authors_df):
    errors = []
    authors_columns_to_check = ['author_email', 'author_name', 'author_affiliation', 'author_name_type']
    valid_identifier_types = ["ORCID", "ISNI", "LCNA", "VIAF", "GND", "DAI", "ResearcherID", "ScopusID", "Other"]
    valid_affiliation_identifier_types = ["ROR", "Other"]
    errors.extend(check_required_fields(authors_df, authors_columns_to_check))
    errors.extend(validate_affiliation_identifier(authors_df, valid_affiliation_identifier_types))
    errors.extend(validate_author_identifier(authors_df, valid_identifier_types))
    return errors

def validate_samples(samples_df, related_resources_df, authors_df, funding_df):
    errors = []
    samples_columns_to_check = ['sample_number', 'description', 'user_keywords', 'sample_type', 'author_emails']
    errors.extend(check_required_fields(samples_df, samples_columns_to_check))
    errors.extend(check_unique_sample_number(samples_df))
    errors.extend(validate_epsg(samples_df))
    errors.extend(validate_sample_depth(samples_df))
    errors.extend(validate_elevation(samples_df))
    errors.extend(validate_sample_type(samples_df))
    errors.extend(validate_match_related_resource_url(samples_df, related_resources_df))
    errors.extend(validate_match_user_email(samples_df, authors_df))
    errors.extend(validate_match_project_identifier(samples_df, funding_df))
    errors.extend(validate_acquisition_date(samples_df))
    
    return errors