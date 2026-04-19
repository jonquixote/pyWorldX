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
        "filename": "q85_l2_validation.md",
        "question": "How should the L²[0,T] integral norm be implemented in Python alongside NRMSD? What are the discretization and normalization requirements, and how should it be weighted relative to the dual ROC-Value metric?"
    },
    {
        "filename": "q86_central_registrar.md",
        "question": "Provide the complete step-by-step algorithmic sequence of one CentralRegistrar RK4 sub-step, from state vector snapshot through demand collection, ceiling evaluation, SupplyMultiplier resolution, and derivative finalization, in enough detail to translate directly to Python."
    },
    {
        "filename": "q87_rip_sectors.md",
        "question": "Are any of the original pyworld3 sector implementations (FCAOR lookup table, PPOLX single-stock, instant cash-box capital) still active during a calibration run, or have they been fully superseded? What is the correct way to verify that no legacy World3 equations are contaminating new sector outputs?"
    },
    {
        "filename": "q88_spin_up_1850.md",
        "question": "What are the recommended 1850 initial conditions for each major stock (NRI, IC, SC, AL, atmospheric GHG, persistent pollution, population) to achieve a stable pre-industrial equilibrium before entering the 1900 calibration window?"
    },
    {
        "filename": "q89_nrmsd_weights.md",
        "question": "Cite the source and provide the full weight table across all observable sectors for the Sector-Weighted NRMSD. Are these weights appropriate and do they come from the Nebel 2023 recalibration literature?"
    },
    {
        "filename": "q90_finance_capital_init.md",
        "question": "What is the correct initialization order for Finance ↔ Capital at t=1900? What is the recommended opening Liquid Funds balance, and how should IC be monetized before the first RK4 step without creating a circular dependency?"
    },
    {
        "filename": "q91_dt_reconciliation.md",
        "question": "What is the minimum stable dt for each sector family (finance/energy, resources, agriculture, population), and what is the recommended multi-rate scheduler configuration that uses 1/512 only for stiff sub-systems while running slower sectors at dt=1/64 or coarser?"
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
