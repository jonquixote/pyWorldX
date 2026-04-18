import subprocess
import os
import re

BIN = "/Users/johnny/nl_venv/bin/notebooklm"
OUT_DIR = "/Users/johnny/pyWorldX/Notebook Conversations/Raw_Q_and_A"
env_vars = os.environ.copy()
env_vars["NOTEBOOKLM_HOME"] = os.path.expanduser("~/.notebooklm/profiles/default")

print("Setting context to Notebook 27a3ae4c ...")
subprocess.run([BIN, "use", "27a3ae4c"], env=env_vars, check=True)

queries = [
    {
        "filename": "q80_human_capital_analytical_test.md",
        "question": "When testing the Human Capital differential equation (dH/dt = -0.069*H with 10-year half-life) using RK4 at dt=1.0, it deviates from the exact analytical solution. The canonical R-I-P test uses an extremely tight 1e-4 tolerance. Should we use a smaller dt for SEIR/Human Capital, or loosen the analytical test tolerance to just verify half-life ≈ 0.5?"
    },
    {
        "filename": "q81_human_capital_coupling_production.md",
        "question": "Regarding Human Capital coupling to Capital: I multiplied the entire industrial_output by human_capital_multiplier at the end of the production chain. But q64 specifies Cobb-Douglas Q = A × K^α × R^β × H^(1-α-β). My implementation is simpler: IO = IC × (1-FCAOR) × CUF / ICOR × H. Is my approximation acceptable for Phase 2, or must we refactor the core production function to true Cobb-Douglas?"
    },
    {
        "filename": "q82_human_capital_energy_demand.md",
        "question": "Currently, the Human Capital sector does NOT broadcast energy_demand to the CentralRegistrar (as per q70). It reads Service_Output_Per_Capita but has no direct energy allocation. Since education requires physical infrastructure (schools, transport), does H need an explicit energy_demand, or is its energy footprint implicitly covered by the Service Sector's energy footprint?"
    },
    {
        "filename": "q83_conftest_fixtures_parameterization.md",
        "question": "In the pytest conftest.py, we have `phase1_all_sectors` fixture that creates fresh sector instances each time using default parameters. Is there an officially recommended pattern in pyWorldX to test sectors isolated with custom parameters (like we do with parameter_overrides in scenarios), inside the pytest suite?"
    },
    {
        "filename": "q84_data_pipeline_mapping.md",
        "question": "We found three new data sources: 1) NOAA GML / GCB 2024/2025 netCDF for CO2 growth rates and flux partitioning. 2) EIA International End-Use Dataset (April 2026) for sectoral energy consumption. 3) USDA NRCS SSURGO/STATSGO2 for Soil Phosphorus Bioavailability. How should these specific datasets map to the Phase 2 sectors? Which parameters and calibration targets should they specifically inform?"
    }
]

def clean_output(text: str) -> str:
    text = re.sub(r'Continuing conversation.*?\n', '', text)
    text = re.sub(r'Resumed conversation:.*?\n', '', text)
    text = re.sub(r'Exit code:.*?\n', '', text)
    return text.strip()

os.makedirs(OUT_DIR, exist_ok=True)

for item in queries:
    query = item["question"]
    filename = item["filename"]
    
    print(f"Asking {filename}...")
    result = subprocess.run([BIN, "ask", query], env=env_vars, capture_output=True, text=True)
    
    cleaned = clean_output(result.stdout)
    out_path = os.path.join(OUT_DIR, filename)
    
    with open(out_path, "w") as f:
        f.write(f"**Question:** {query}\n\n---\n\n**Answer:**\n{cleaned}\n")
        
    print(f"Saved cleanly to {filename}")
