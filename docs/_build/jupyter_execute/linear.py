#!/usr/bin/env python
# coding: utf-8

# # A Basic Discounted Cash Flow Valuation

# 
# 
# Chapter 1 showcases the structure and functionality of a *basic* Discounted Cash
# Flow (DCF) Valuation in use in a real estate project. In this notebook, the core
# computational objects (classes), their functionality, and how they are composed
# together into a valuation model are outlined:

# 1. Import required modules from the Rangekeeper and other libraries:

# In[1]:


# Import standard libraries:
import pandas as pd
import os
from dateutil import parser

# Import Rangekeeper:
import rangekeeper as rk


# ## Basic Elements of a Proforma
# 
# ### A 'Flow'
# The core element of a Cash Flow analysis is the cash flow; a sequence of
# *movements* of currency (whether positive -- *inflow*, or negative -- *outflow*),
# where each movement is associated with a *date* and a *quantity*. A cash flow
# is also sometimes referred to as a 'line item', which is a way of designating
# the subject of flows, e.g.: "Operational Expenses", or "Income from Building 2's
# Parking"
# 
# A cash flow is implemented in Rangekeeper as a `Flow` object (from the flux module),
# which uses a pandas `Series` object to encapsulate the 'movements' of material
# (with specified units, like currency, energy, mass, etc) that occur at specified
# dates.
# 
# Note: the `Flow`'s movements Series index is pandas `DatetimeIndex`, and its
# values are `float`s.

# In[2]:


currency = rk.measure.register_currency('USD', registry=rk.measure.Index.registry)

transaction_dates = ['2020-01-01', '2020-01-02', '2019-01-01', '2020-01-01', '2020-12-31']
transaction_amounts = [100, 200, 300, 400, 500]

movements = pd.Series(data=dict(zip([parser.parse(date) for date in transaction_dates], transaction_amounts)))

cash_flow = rk.flux.Flow(
    name='Operational Expenses',
    movements=movements,
    units=currency.units)

print(cash_flow)
print(os.linesep)
print('Cash Flow Index: ' + str(cash_flow.movements.index))
print(os.linesep)

print(cash_flow.movements.info())


# As you can see, a `Flow` has three properties:
# 1. it's Name,
# 2. a Pandas Series of date-stamped amounts ('Movements'), and
# 3. the units of the movement's amounts
# 
# * Note that the movements can be in any (temporal) order

# ### Structuring a Table of Cash Flows
# Given a simple example of such a DCF valuation for a stylized commercial rental
# property, Rangekeeper provides enhanced functionality for constructing and structuring
# the proforma:
# 
# ![Table 1.1 From Geltner & De Neufville, 2018](resources/FaREVuU-table1.1.jpg)
# 
# ### A 'Span'
# A Span is a pd.Interval of pd.Timestamps that bound its start and end dates.
# Spans are used to define intervals of time that encompass the movements of a Flow.
# 

# In[3]:


s# Define a Span:
start_date = pd.Timestamp('2000-01-01')
num_periods = 10
operation_span = rk.span.Span.from_num_periods(
    name='Operation',
    date=start_date,
    period_type=rk.periodicity.Type.year,
    num_periods=num_periods)
print(operation_span)


# ### A 'Projection'
# A projection takes a value and casts it over a sequence of periods according to a
# specified logic. There are two classes of logic:
# 1. Extrapolation, which takes a starting value and generates a sequence
# of values from that initial one, and
# 2. Distribution, which takes a total value and subdivides it over a range

# In[ ]:


# Define a Projection:
compounding_rate = 0.02
projection = rk.projection.Extrapolation(
    form=rk.projection.Extrapolation.Compounding(rate=compounding_rate),
    sequence=operation_span.to_index(period_type=rk.periodicity.Type.year))


# Projections are used in the construction of Flows:
# 

# In[ ]:


# Define a compounding Cash Flow:
initial_income = 100
potential_gross_income = rk.flux.Flow.from_projection(
    value=initial_income,
    proj=projection,
    units=currency.units)
print(potential_gross_income)


# 2.1 Initiate Project Parameters:

# In[ ]:


# # 2.1.1: Unit Mix:
# unit_mix = {
#     Apartment.Type.B1B1B0: 0,
#     Apartment.Type.B1B1B1: 1,
#     Apartment.Type.B2B1B1: 0,
#     Apartment.Type.B2B1B2: 0,
#     Apartment.Type.B2B2B0: 0,
#     Apartment.Type.B2B2B1: 2,
#     Apartment.Type.B3B2B0: 0,
#     Apartment.Type.B3B2B1: 1
#     }
#
# property_params = {
#     'gla': 750.0,
#     'sales_price_per_gfa': 6875,
#     }
#
# project_params = {
#     'start_date': pd.Timestamp('2021-01-01'),
#     'periodicity': Periodicity.Type.month,
#     'preliminaries_duration': 2,
#     'construction_duration': 4,
#     'sales_duration': 3,
#     'sales_fee_rate': 0.02,
#     'construction_interest_rate_pa': 0.03,
#     'parking_ratio': 1,
#     'units': Units.Type.AUD,
#     'margin_on_cost_reqd': 0.20
#     }
# models.linear.compose_spans(project_params)
# models.linear.compose_apartments(unit_mix=unit_mix, project_params=project_params)


# In[ ]:


# # Display Project Params in a DataFrame:
# project_params_df = pd.DataFrame.from_dict(
#     data={key: [str(value)] for key, value in project_params.items()},
#     orient='index',
#     columns=['project_params'])
# display(project_params_df)
#


# 2.2 Compose Preliminaries:

# In[ ]:


# # Prelims:
# preliminary_costs_index = {
#     'design_planning_engineering_cost': 20000.0,
#     'survey_geotech_cost': 5000.0,
#     'permitting_inspections_certifications_cost': 10000.0,
#     'legal_title_appraisal_cost': 3500.0,
#     'taxes_insurance_cost': 1500.0,
#     'developer_project_management_cost': 50000.0
#     }
#
# preliminaries = models.linear.compose_prelim_costs(
#     preliminaries_costs_index=preliminary_costs_index,
#     project_params=project_params
# )
# display("Preliminaries: ")
# display(preliminaries.frame.transpose())
#
# display("Preliminaries Subtotals: ")
# display(preliminaries.collapse().frame.transpose())
#
# display("Preliminaries Totals: ")
# display(preliminaries.collapse().sum(name='preliminaries_total').to_stream(periodicity=project_params['periodicity']).frame.transpose())


# 2.3 Compose Build Costs:

# In[ ]:


# # Build Costs:
# build_costs_index = {
#     'construction_cost_shell_pergfa': 1250.0,
#     'construction_cost_cores_pergfa': 3000.0,
#     'siteworks_cost_pergla': 35.0,
#     'parking_cost_per_stall': 15000.0,
#     'utilities_cost': 10000.0
# }
#
# build_costs = models.linear.compose_build_costs(
#     build_costs_index=build_costs_index,
#     property_params=property_params,
#     project_params=project_params
# )
#
# display("Build Costs: ")
# display(build_costs.frame.transpose())
#
# display("Build Costs Subtotals: ")
# display(build_costs.collapse().frame.transpose())
#
# display("Build Costs Totals: ")
# display(build_costs.collapse().sum(name='build_costs_total').to_stream(periodicity=project_params['periodicity']).frame.transpose())


# 2.4 Compose Financing Costs:

# In[ ]:


# # Finance Costs:
# finance_costs = models.linear.compose_finance_costs(
#     project_params=project_params,
#     preliminaries_costs=preliminaries,
#     build_costs=build_costs
# )
#
# display("Financing Costs Calculation: ")
# display(finance_costs.frame.transpose())#_year.frame.transpose())
#
# interest_costs = finance_costs.extract('interest').to_stream(periodicity=project_params['periodicity'])
#
# display("Interest Costs: ")
# display(interest_costs.frame.transpose())
#
# display("Interest Cost Total: ")
# display(interest_costs.collapse().frame.transpose())


# 2.5 Compose Net Development Costs:

# In[ ]:


# net_development_costs = flux.Stream.merge(
#     streams=[preliminaries, build_costs, interest_costs],
#     name='net_development_costs',
#     periodicity=project_params['periodicity'])
#
# display("Net Development Costs: ")
# display(net_development_costs.frame.transpose())
#
# display("Net Development Costs Subtotals: ")
# display(net_development_costs.collapse().frame.transpose())
#
# display("Net Development Costs Total: ")
# display(net_development_costs.collapse().sum(name='net_development_costs_total').to_stream(periodicity=project_params['periodicity']).frame.transpose())
#


# 3 Compose Revenues:

# In[ ]:


# revenues = models.linear.compose_revenues(
#     property_params=property_params,
#     project_params=project_params)
#
# display("Revenues: ")
# display(revenues.frame.transpose())
#
# display("Revenues Subtotals: ")
# display(revenues.collapse().frame.transpose())
#
# display("Revenues Totals: ")
# display(revenues.collapse().sum(name='revenues_total').to_stream(periodicity=project_params['periodicity']).frame.transpose())


# 4 Net Development Revenue:

# In[ ]:


# ndr_stream = flux.Stream(
#     name='net_development_revenue',
#     flows=[net_development_costs.sum().invert(), revenues.sum()],
#     periodicity=project_params['periodicity'])
#
# display("Net Development Revenue: ")
# display(ndr_stream.frame.transpose())
#
# net_development_revenue = ndr_stream.sum()
# display(net_development_revenue.to_stream(periodicity=project_params['periodicity']).frame.transpose())
# display(net_development_revenue.sum().to_stream(periodicity=project_params['periodicity']).frame.transpose())


# 5 Project-level Returns:

# In[ ]:


# margin = (project_params['margin_on_cost_reqd'] * net_development_costs.collapse().sum().movements)[0]
# residual_land_value = net_development_revenue.sum().movements[0] - margin
# display("Residual Land Value: " + str(residual_land_value))
#
# investment_flow = flux.Flow.from_dict(
#     name='investment',
#     movements={project_params['start_date']: (-1) * residual_land_value },
#     units=project_params['units'])
# ndr_stream.append(flows=[investment_flow])
#
# net_development_flow = ndr_stream.sum()
# display(net_development_flow.to_stream(periodicity=project_params['periodicity']).frame.transpose())
#
# irr = net_development_flow.xirr()
# display("Project IRR: " + str(irr))


