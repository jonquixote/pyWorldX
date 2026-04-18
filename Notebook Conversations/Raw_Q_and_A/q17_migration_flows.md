**Question:** In a multi-node regional model, how do system dynamics models typically model mass migration driven by regional collapse? What triggers the population flow equations, and how does the influx alter the destination's Capital and Service density variables?

---

Answer:
In multi-node regional models like **WORLD6** or the planned **World4/PEEC**, 
mass migration is typically modeled as a **population flow ($P_{flow}$)** 
between regional stocks, where the rate of flow is determined by the **relative 
disparity in quality-of-life variables** between nodes [1, 2]. While the 
original World3 is a global aggregate, its equations are designed to be 
scale-invariant, allowing for the addition of "migration and trade flows across 
boundaries" to represent specific nations or regions [1, 3].

### 1. Triggers for Population Flow Equations
Population flow in system dynamics is endogenously triggered by **attractiveness
differentials** between the "periphery" and the "core" [4]. These triggers 
include:

*   **Standard of Living Disparities:** The primary driver is the gap in 
**Material Standard of Living ($MSL$)** or **GDP per person** between regions 
[5-7]. As one region experiences biophysical stagnation—where extraction costs 
rise and net energy profits fall—the resulting economic decline creates a "push"
factor [8, 9].
*   **Regional Collapse Signals:** Sharp declines in local **Food Per Capita 
($FPC$)** or **Service Output Per Capita** act as critical thresholds [10, 11]. 
The literature notes that social disintegration tends to "creep from the 
periphery towards the core" as regions with less capital to "throw at their 
problems" hit biophysical limits first [4].
*   **Resource and Environmental Shocks:** Sudden "fast-process shocks," such as
climate-induced crop failures or the exhaustion of regional groundwater, 
physically force populations out of a degraded "basin of attraction" [12, 13].

### 2. Impact on Destination Capital and Service Density
When a destination node receives a mass influx of people, it triggers a 
**negative feedback loop** that alters the density of its industrial and social 
infrastructure:

*   **Dilution of Capital Density:** Industrial capital ($IC$) is a stock that 
accumulates slowly through investment [14]. A sudden rise in population ($P$) 
immediately decreases **Industrial Output Per Capita ($IOPC$)**, as the same 
physical production capacity must now support more individuals [15, 16]. This 
"capital dilution" can starve the region of the reinvestment needed to maintain 
its own complex structures [17, 18].
*   **Service Density Erosion:** The **Service Capital stock ($SC$)**, which 
represents infrastructure like schools and hospital laboratories, is fixed in 
the short term [9, 19]. An influx causes **Services Per Capita** to drop, 
reducing the "Effective Health Services" available to the original population 
[20, 21].
*   **The 'Crowding' Multiplier:** In destination nodes, rising population 
density triggers a **Death-Rate-from-Crowding Multiplier ($DRCM$)** [22, 23]. 
This multiplier reduces life expectancy as the physical and psychological 
pressures of high population density relative to the available land and service 
base increase [24, 25].

By modeling these flows, system dynamics reveals a **"contagion of collapse"** 
[26, 27]. A region that was previously stable can be pushed into an **overshoot 
and collapse mode** by an influx that exceeds its "carrying capacity," as the 
destination's capital and services can no longer be replenished fast enough to 
meet the expanded demand [28-30].

Conversation: aa4adc9c-0d1b-4d26-b97a-d7266fef0048 (turn 1)
