# /fastapi/main.py
import random
from batch.validator import validate_user_keywords
from fastapi import FastAPI, File, UploadFile, HTTPException
import pandas as pd
import json
import sys
import requests
from pathlib import Path
import urllib
from io import BytesIO
import uvicorn

app = FastAPI()


@app.get("/")
async def read_root():
    return {"Hello": "World!!!!"}


@app.post("/")
async def create_package(file: UploadFile = File(...)):
    ckan_url = "http://ckan-dev:5000"
    headers_dict = {
        "Authorization": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJqdGkiOiJiQnRlM1FFOFA3RkRJa3J5ZXYyLVZ4NWdPTWZxQTlrNnpadnVwU2hXQmhRIiwiaWF0IjoxNzEzMTY0ODE4fQ.Ergt_qhQJqXMHyknjOWMS8SdQqd3WnpgaodkvQJXmIc",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    url_path = Path("api") / "3" / "action" / "package_create"

    url = f"{ckan_url}/{url_path}"

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