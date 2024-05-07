# /fastapi/main.py
import random
from batch.validator import validate_user_keywords
from fastapi import FastAPI, File, UploadFile, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
import pandas as pd
import json
import sys
import requests
from pathlib import Path
import urllib
from io import BytesIO
import uvicorn

app = FastAPI()

api_key_header = APIKeyHeader(name="Authorization", auto_error=True)


@app.get("/")
async def read_root():
    return {"Hello": "World!!!!"}


@app.post("/")
async def create_package(api_token: str = Security(api_key_header), file: UploadFile = File(...)):
    if not api_token:
        raise HTTPException(status_code=401, detail="API token is required")

    ckan_url = "http://ckan-dev:5000"
    # headers_dict = {
    #     "Authorization": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJqdGkiOiJiQnRlM1FFOFA3RkRJa3J5ZXYyLVZ4NWdPTWZxQTlrNnpadnVwU2hXQmhRIiwiaWF0IjoxNzEzMTY0ODE4fQ.Ergt_qhQJqXMHyknjOWMS8SdQqd3WnpgaodkvQJXmIc",
    #     "Content-Type": "application/x-www-form-urlencoded",
    # }
    url_path = Path("api") / "3" / "action" / "package_create"
    url = f"{ckan_url}/{url_path}"

    # Validate the token with CKAN
    validation_response = requests.get(url, headers={"Authorization": api_token})
    if validation_response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid API token.")

    headers_dict = {
        "Authorization": api_token,
        "Content-Type": "application/x-www-form-urlencoded",
    }

    response = await process_excel(file)
    results = []

    for item in response:
        in_dict = urllib.parse.quote(json.dumps(item))
        r = requests.post(url, data=in_dict, headers=headers_dict)
        try:
            resp = json.loads(r.text)
            results.append(resp)
            print(f"\nPACKAGE INFO: {resp=}")
        except json.JSONDecodeError as jde:
            print(f"ERROR - {jde}")
            results.append({"error": str(jde)})
    return {"results": results}


async def process_excel(file: UploadFile = File(...)):
    try:
        # Read the content of the uploaded file into a BytesIO object
        content = await file.read()
        excel_data = BytesIO(content)
        sheets = ["samples", "authors", "related_resources"]
        dfs = {}
        for sheet in sheets:
            excel_data.seek(0)  # Reset file pointer to the beginning
            dfs[sheet] = pd.read_excel(excel_data, sheet_name=sheet, na_filter=False, engine="openpyxl")
        samples_df = dfs["samples"]
        authors_df = dfs["authors"]
        related_resources_df = dfs["related_resources"]

        # Initialize samples data structure
        samples_data = []

        # Iterate over each row in the samples DataFrame
        for _, row in samples_df.iterrows():
            sample = row.to_dict()

            # Process author_emails
            author_emails = [
                email.strip() for email in sample.get("author_emails", "").split(";")
            ]
            matched_authors = authors_df[authors_df["author_email"].isin(author_emails)]
            sample["author"] = json.dumps(matched_authors.to_dict("records"))

            # Process related_resources_urls
            related_resource_urls = [
                url.strip()
                for url in sample.get("related_resources_urls", "").split(";")
            ]
            matched_resources = related_resources_df[
                related_resources_df["related_resource_url"].isin(related_resource_urls)
            ]
            sample["related_resource"] = json.dumps(matched_resources.to_dict("records"))
            sample['user_keywords'] = validate_user_keywords(sample['user_keywords'])
            defaults = {
                "publisher_identifier_type": "ror",
                "publisher_identifier": "https://ror.org/04s1m4564",
                "publication_date": "2024-03-08",
                "notes": "A long description of my dataset",
                "publisher": "AuScope",
                "resource_type": "physicalobject",
                "owner_org": "testing",
                "location_choice": "noLocation"
            }
            sample.update(defaults)

            sample["name"] = "ckan-api-test-" + str(random.randint(0, 10000))
            samples_data.append(sample)
        return samples_data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Error reading sheet: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await file.close()  # Ensure the uploaded file is closed

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=80, reload=True)
