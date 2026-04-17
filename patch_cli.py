
with open("data_pipeline/cli.py", "r") as f:
    content = f.read()

old_str = """    elif source_id == "gcp" or source_id.startswith("gcp_"):
        from data_pipeline.connectors.gcp import fetch_gcp
        return fetch_gcp(config)"""

new_str = """    elif source_id == "gcp" or source_id.startswith("gcp_"):
        from data_pipeline.connectors.gcp import fetch_gcp
        return fetch_gcp(config)
    elif source_id == "gcb":
        from data_pipeline.connectors.gcb import fetch_gcb
        return fetch_gcb(config)
    elif source_id == "ssurgo":
        from data_pipeline.connectors.ssurgo import fetch_ssurgo
        return fetch_ssurgo(config)"""

if old_str in content:
    content = content.replace(old_str, new_str)
    with open("data_pipeline/cli.py", "w") as f:
        f.write(content)
    print("Successfully patched cli.py")
else:
    print("Could not find the target string in cli.py")
