**Question:** We're adding a Human Capital stock to pyWorldX's production function: Q = A * K^alpha * R^beta * H^(1-alpha-beta), where H is human capital. What should the ODE for H be? The literature suggests dH/dt = EducationRate - SkillDegradationRate - MortalityLoss. How should EducationRate be parameterized — as a function of Service Capital per capita, or as a function of dedicated education investment? What is the typical SkillDegradationRate (obsolescence of skills) in system dynamics models? And critically, what should the output elasticity of H be — the literature suggests 50-60%, but does this vary with development level (higher in knowledge economies, lower in resource extraction economies)?

---

Answer:
Answer:
**The ODE for Human Capital ($H$)** in your 4-cohort population tracker should indeed be 
structured as $\frac{dH}{dt} = \text{EducationRate} - \text{SkillDegradationRate} - 
\text{MortalityLoss}$ [1]. Here is how the literature specifies the parameterization and 
elasticity of these components:

**1. Parameterizing the EducationRate**
The `EducationRate` should not be modeled as an isolated, dedicated education investment flow. 
Instead, the literature dictates it must be parameterized as a function of the **Education Index
(EI)**, which is directly driven by **Service Output Per Capita (SOPC)** [2]. 
*   The exact mathematical linkage is `EducationRate = f(EI) * LaborForce` [2].
*   Because EI relies on Service Capital, this wires in a critical vulnerability: during a 
resource crisis, the system will programmatically divert capital away from Services to maintain 
industrial extraction [3]. This diversion starves Service Capital, causing SOPC to fall, which 
in turn drags down the Education Index and chokes off the `EducationRate` [2, 3]. 

**2. The Typical SkillDegradationRate**
The `SkillDegradationRate` represents the loss of skills due to "obsolescence, lack of practice,
or the failure of intergenerational knowledge transfer" [1]. **The provided literature does not 
specify an exact numerical constant or typical percentage for this decay rate.** 
However, it strictly defines its structural role as the **"maintenance gap for humans"** [2]. 
You must balance this parameter so that if the `EducationRate` falls below the 
`SkillDegradationRate`, the Human Capital stock triggers a non-linear collapse, causing a 
broad-front systemic failure because industrial machines ($K$) can no longer operate at their 
designed efficiency [2, 4].

**3. Output Elasticity and Development Levels**
The literature confirms that the output elasticity of skilled labor/human capital 
($1-\alpha-\beta$) generally accounts for **50–60% of all value generated in modern systems** 
[5]. 

Regarding how this varies with development levels, the PEEC/World4 framework indicates that the 
nature of labor productivity fundamentally shifts as economies mature:
*   **Resource and Industrial Economies:** History shows that it is relatively "simple to 
automatise the production of food and industrial output" [6]. In these earlier stages of 
development, physical capital ($K$) and resources ($R$) can more easily substitute for labor. 
*   **Mature / Knowledge Economies:** As an economy develops, the percentage of GDP in the 
primary and secondary sectors naturally declines, and the workforce shifts heavily into the 
tertiary (services) and quaternary (care/culture) sectors [6, 7]. The literature emphasizes that
it is "harder to computerise services, and difficult to robotise care" [6]. 

Therefore, in mature economies, human capital becomes an even more rigid constraint. Because 
labor in these sectors cannot be easily automated, **productivity growth natively slows down** 
[6]. The 50-60% elasticity becomes a severe bottleneck; if the system starves its education 
pipeline to pay for rising resource extraction costs, the highly-developed knowledge economy 
will suffer a "Human Capital Death Spiral" that permanently cripples industrial output [4, 8].
