from src.parser import DoclingToStructuredExtractor
from src.settings import load_settings
import time
import json
import os


def upload_json_to_gcs(
    gcs_manager, bucket_name: str, folder: str, filename: str, data: dict
):
    gcs_manager.upload_json(bucket_name, f"{folder}/{filename}.json", data)


def main():
    settings = load_settings(env_dev=True)
    parser = DoclingToStructuredExtractor()
    start = time.time()
    doc_name = "422599 אפיון מודול מעצרים חדש_docling.json"
    main_json, images_json = parser.parse_structured_data(doc_name)
    print(f"\u23f1\ufe0f extract_pdf took {time.time() - start:.2f} seconds")

    base_name = os.path.basename(doc_name).replace("_docling.json", "")
    bucket_name = settings.INPUT_BUCKET_NAME
    parser.gcs_manager.upload_json(
        bucket_name, f"{base_name}/main_json.json", main_json
    )
    parser.gcs_manager.upload_json(
        bucket_name, f"{base_name}/images_json.json", images_json
    )
    print(
        f"\u2714\ufe0f  \u05d4\u05e2\u05dc\u05d9\u05ea\u05d9 main_json \u05d5-images_json \u05dc-gs://{bucket_name}/{base_name}/"
    )


if __name__ == "__main__":
    main()
