**Question:** For the non-linear depreciation upgrade, the literature replaces linear ALIC with an exponential phi(MaintenanceRatio) multiplier. Since exponential decay curves can cause extreme numerical stiffness when the Maintenance Gap drops below 1.0, what precise mathematical function or lookup-table shape is recommended for 'phi' to ensure the RK4 solver maintains stability at 1/512 year timesteps?

---

Answer:
The provided literature and project documentation do not specify a precise 
mathematical equation or exact lookup-table coordinates for the 
$\phi(\text{MaintenanceRatio})$ multiplier. 

However, the sources do define the required behavioral shape of the curve and 
explain how the architecture handles the resulting numerical stiffness without 
needing to artificially flatten the mathematics:

**1. The General Shape of the $\phi$ Multiplier**
The literature establishes that the multiplier must act as a bounded exponential
curve or lookup table to simulate the reality that physical complexes unravel 
non-linearly when maintenance fails [1]:
* **Baseline:** When the ratio of Actual Maintenance Investment to Required 
Maintenance is $\geq 1.0$, $\phi$ remains flat at **1.0**, representing standard
baseline depreciation (the normal Average Lifetime of Industrial Capital) [2, 
3].
* **The Exponential Spike:** As the ratio drops below 1.0 (when an exhausted 
debt pool and energy scarcity drain Liquid Funds), $\phi$ spikes exponentially 
to represent the rapid physical unraveling of infrastructure [1, 2]. 
* **The Boundary:** To prevent mathematical infinities when maintenance drops to
absolute zero, the function is bounded, typically capping the multiplier at a 
maximum spike of **2.0 or 4.0** times the normal decay rate [3].

**2. Handling Numerical Stiffness Natively**
To ensure the RK4 solver maintains stability when this exponential collapse 
triggers, the literature does not prescribe softening the $\phi$ curve itself. 
Instead, the extreme differential stiffness and potential "numeric explosions" 
across the interlinked debt and capital arrays are **natively bridged by the 
1/512 year timestep** [4]. 

By heavily bumping the integration frequency to this 1/512 dt resolution, the 
solver naturally smooths the sharp financial flow and physical degradation 
feedback logic in the Python arrays [4]. The engine can afford to digest the 
sudden exponential shock of the infrastructure decay step-by-step without 
crashing the differential equations [4, 5].

**3. State-Gating as a Structural Safeguard**
In addition to the stiff timestep, the architecture relies on "State-Gating" to 
prevent solver deadlocks. The rules dictate that every cross-sector feedback 
loop must contain at least one Integrator (Level) or significant delay [6]. 
Because Industrial Capital, Liquid Funds, and Total Debt are all explicitly 
defined as discrete Integrators rather than instantaneous auxiliary variables, 
the collision between the frozen debt pool and the exponentially accelerating 
depreciation resolves smoothly through time across the sub-steps, successfully 
bypassing zero-delay algebraic loops [4, 6].

Conversation: 9ef90f0e-5cf1-4f69-9744-ad6246e124cf (turn 1)
