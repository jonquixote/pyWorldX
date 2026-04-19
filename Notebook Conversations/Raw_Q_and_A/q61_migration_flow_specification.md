**Question:** In our pyWorldX regional model, how should migration flows between regions be mathematically specified? The literature suggests migration is driven by attractiveness differentials in Material Standard of Living, food security, and pollution exposure. What is the correct functional form for the migration rate? Is it proportional to the attractiveness gap, or is there a threshold below which migration doesn't occur? How should the destination region's carrying capacity be affected by incoming population?

---

Answer:
Answer:
In the `pyWorldX` regional architecture, migration flows between regions are mathematically 
specified using **replicator dynamics**, a continuous mathematical approach drawn from 
evolutionary game theory used to model boundedly rational decision-making [1]. 

**1. The Functional Form of the Migration Rate**
The migration rate is **strictly proportional to the attractiveness gap** (the payoff 
difference) between regions; there is no hard threshold below which migration completely stops, 
as long as a disparity exists [1]. 

The differential equation governing the population flow ($dU/dt$) transitioning out of a region 
is modeled as:
$dU/dt = m \cdot U \cdot (\text{Local Wellbeing} - \text{Outside Wellbeing})$ [1]

*   **$U$** is the current regional population [1].
*   **$m$** represents the community’s responsiveness to differences in well-being inside versus
outside the system [1].
*   The "Wellbeing" parameters are dynamic aggregates of the regional disparities in Material 
Standard of Living ($MSL$), Food Per Capita ($FPC$), and environmental degradation [2]. 

Because the flow is proportional to the payoff difference, migration scales continuously, 
accelerating non-linearly as the gap in quality-of-life widens between a collapsing "periphery" 
and a wealthier "core" [1, 2].

**2. Impact on the Destination Region's Carrying Capacity**
When a destination node receives a mass influx of migrants, the model does not assume a seamless
or immediate expansion of carrying capacity. Instead, the incoming population triggers a severe 
**negative feedback loop** that mechanically degrades the destination's systemic stability 
through three primary mathematical pathways [3]:

*   **Dilution of Capital Density:** Industrial Capital ($IC$) accumulates slowly through 
delayed investments. A sudden surge in population immediately dilutes the **Industrial Output 
Per Capita ($IOPC$)**, because the fixed physical production capacity must now support a larger 
denominator of individuals. This starves the region of the surplus reinvestment needed to 
maintain its own complex structures [3].
*   **Service Density Erosion:** Service Capital ($SC$), representing infrastructure like 
hospitals and schools, is highly rigid in the short term. The influx causes Services Per Capita 
to plummet, which mechanically reduces the "Effective Health Services" available to the 
aggregate population, driving up mortality [3].
*   **The Crowding Multiplier:** The rapid increase in regional population density forces the 
**Death-Rate-from-Crowding Multiplier ($DRCM$)** upward. This reduces overall life expectancy 
due to the physical and psychological pressures of high population density relative to the 
available land and infrastructure [3].

**The "Contagion of Collapse"**
By structuring the migration matrix this way, the simulation produces a phenomenon known as the 
**"Contagion of Collapse"** [4, 5]. A destination region that was previously in a stable, 
sustainable equilibrium can be forced into a systemic overshoot and collapse simply because its 
capital matrices and service stocks are mechanically diluted beyond their replacement capacity 
by the rapid influx of population [4, 5].
