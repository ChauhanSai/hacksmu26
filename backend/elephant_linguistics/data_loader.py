"""Google Cloud Storage data loader for elephant call dataset."""

import os
import pandas as pd


def download_dataset(bucket_name: str, prefix: str, local_dir: str):
    """Download all audio files and metadata from GCS."""
    from google.cloud import storage

    client = storage.Client()
    bucket = client.bucket(bucket_name)

    for blob in bucket.list_blobs(prefix=prefix):
        local_path = os.path.join(local_dir, blob.name.replace(prefix, '', 1))
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        blob.download_to_filename(local_path)
        print(f"Downloaded: {blob.name}")


def load_metadata(path: str) -> pd.DataFrame:
    """Load metadata from CSV or JSON."""
    if path.endswith('.csv'):
        return pd.read_csv(path)
    if path.endswith('.json'):
        return pd.read_json(path)
    raise ValueError(f"Unsupported metadata format: {path}")
