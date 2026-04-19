**Question:** What is the correct functional form for r(T) — the temperature-dependent intrinsic regeneration rate of ecosystem services? In our model, dESP/dt = r(T) * ESP * (1 - ESP) - DegradationRate. Should r(T) be a linear decline with temperature, a Gaussian curve, a piecewise function with ecosystem-specific thresholds, or something else? What are the typical parameter values for global ecosystem regeneration sensitivity to warming?

---

Answer:
Answer:
The provided literature and project documentation do not specify the exact mathematical 
functional form (such as a Gaussian curve, linear decline, or piecewise function) for $r(T)$, 
nor do they provide the specific numerical parameter values for global ecosystem regeneration 
sensitivity to warming. You will need to independently verify those specific functional shapes 
and parameters from external ecological or Earth system literature.

However, the sources do dictate the structural and behavioral characteristics that this 
temperature-dependent regeneration rate must exhibit within your architecture:

**1. Non-Linear Thresholds Over Linear Declines**
The literature emphasizes that ecosystems do not respond to climate stress with simple, linear 
predictability. Instead, they are characterized by non-linear responses and tipping points [1, 
2]. This suggests that $r(T)$ should be modeled using a threshold-gated or piecewise approach 
rather than a gentle linear decline. The regenerative capacity remains relatively functional 
until a critical thermal limit is breached, at which point the system experiences a "precipitous
decline" and flips into a completely different state (such as desertification) [3]. 

**2. Hysteresis and Irreversibility**
The equations governing your ecosystem regeneration must account for hysteresis. If a thermal 
threshold is crossed and the ecosystem collapses, simply lowering the temperature back to normal
will not restore the regeneration rate $r(T)$ [2]. The literature explicitly warns that "you 
can't get back to where you were along the same route that got you to where you are" [2]. This 
means that once an ecosystem or climate tipping point is triggered, the transition is often 
abrupt and irreversible, essentially "locking" $r(T)$ at a diminished capacity even if the 
original warming driver is removed [4].

**3. Amplification via Existing Degradation (The "Rooting Depth" Effect)**
The temperature sensitivity of the ecosystem is not static; it is dynamically amplified by the 
existing level of environmental degradation. The sources illustrate this using the "rooting 
depth" of soil: a long-term, slow degradation of an ecosystem (such as forest fragmentation or 
soil thinning) might go relatively unnoticed until a short-term thermal shock or drought hits 
[3]. Because the degraded system has lost its physical buffering capacity, it cannot sustain 
itself through the warming event, causing the crops to die and the system to collapse [3, 5]. 
Therefore, the sensitivity of $r(T)$ to thermal spikes should mathematically increase as the 
`DegradationRate` lowers the overall physical resilience of the system.
