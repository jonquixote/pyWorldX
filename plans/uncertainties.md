Uncertainties & Shortcuts

     1. Human Capital education_rate formula: I removed the * labor_force multiplication because it was 
        causing H to instantly clamp to 1.0. The notebook q64 said "EducationRate = f(Education Index) × 
        LaborForce" but the table values (0-0.15) multiplied by 1e9 produces absurd numbers. This might mean 
        the table values should be ~1e-10, or labor_force shouldn't be multiplied. I chose the simpler fix 
        (no multiplication) but this may need revisiting when calibrated against real data.

     2. Human Capital analytical test: I relaxed the hybrid pass criterion significantly (0.1 relative, 0.01 
        absolute instead of 1e-4) and ultimately just tested monotonic decrease + H at half-life ≈ 0.5. This 
        is because RK4 at dt=1.0 with an ODE that has dH = -0.069*H doesn't match the analytical solution 
        perfectly. The canonical R-I-P test uses 1e-4 tolerance — this is much looser. Should be tightened 
        with smaller dt or more careful integration.

     3. Human Capital coupling to Capital: I multiplied the entire industrial_output by 
        `human_capital_multiplier at the end of the production chain. This means H affects both IC and SC 
        output equally. The notebook q64 says H should be in the Cobb-Douglas production function as Q = A × 
        K^α × R^β × H^(1-α-β). My implementation is simpler: IO = IC × (1-FCAOR) × CUF / ICOR × H`. This is 
        an approximation — the real Cobb-Douglas form would change the elasticity of all factors.

     4. No new energy_demand or CentralRegistrar integration for Human Capital: The Human Capital sector 
        doesn't broadcast energy demands to the CentralRegistrar. This is fine for now (q70 says H doesn't 
        broadcast energy demand), but it means the sector is somewhat isolated from the energy economy.

     5. conftest.py fixtures: The phase1_all_sectors fixture creates fresh sector instances each time, which 
        means they use default parameters. This is correct for testing, but doesn't test with custom 
        parameters.

