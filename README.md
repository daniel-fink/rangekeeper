<img src="https://github.com/daniel-fink/rangekeeper/blob/v0.2.0/walkthrough/resources/rangekeeper.jpg?raw=true" width="300">

# Rangekeeper
Rangekeeper is an open-source library for financial modelling in real estate 
asset & development planning, decision-making, cashflow forecasting, and 
scenario analysis.

Rangekeeper enables real estate valuation at all stages and resolutions of 
description — from early-stage ‘back-of-the-envelope’ models to detailed 
commercial assessments, and can be completely synchronised with 3D design, 
engineering, and logistics modelling.

It decomposes elements of the Discounted Cash Flow (DCF) Proforma modelling 
approach into recomposable code functions that can be wired together to form a 
full model. More elaborate and worked-through examples of these classes and 
functions can be found in the [walkthrough documentation](https://daniel-fink.github.io/rangekeeper/).

Development of the library follows the rigorous methodology established by 
Profs Geltner and de Neufville in their book [Flexibility and Real Estate Valuation under Uncertainty: A Practical Guide for Developers](https://doi.org/10.1002/9781119106470).


## Structure

This repository is comprised of three separate, but inter-dependent projects:
1. Rangekeeper library source (in Python) 
2. Walkthrough documentation (a Jupyter Book)
3. McNeel Rhinoceros 3D Grasshopper components (to assist the creation of Rangekeeper-compliant objects from 3D models, in C#)

Each project has its own readme to assist setup and dependency resolution.