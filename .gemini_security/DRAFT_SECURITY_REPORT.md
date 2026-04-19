1. **Vulnerability: Insecure Downloader (URL Constant)**
- **ID:** VULN-001
- **Vulnerability:** Potentially Insecure Source (URL is hardcoded constant)
- **Vulnerability Type:** Security
- **Severity:** Low
- **Source Location:** `data_pipeline/connectors/gcb.py`, lines 27-27
- **Data Type:** N/A (Configuration/Source)
- **Line Content:** `URL = "https://zenodo.org/records/14061175/files/Global_Carbon_Budget_2024v1.0.xlsx?download=1"`
- **Description:** The GCB connector fetches data from a hardcoded HTTPS URL. While HTTPS provides transport-layer security, there is no signature or hash verification performed on the downloaded file content, which could lead to accepting malicious or corrupt data if the source is compromised.
- **Recommendation:** Implement file integrity verification (e.g., checksum validation) after the download completes to ensure the file has not been tampered with or corrupted. The current pipeline already computes a checksum (`sha` from `fetch_with_cache`), but it is currently only used for caching purposes. It should be compared against a trusted, pre-known checksum value.