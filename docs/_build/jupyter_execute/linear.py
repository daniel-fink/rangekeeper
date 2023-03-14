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
import os
import math
import pandas as pd
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

# First we initialize the currency used in our Proforma:

# In[2]:


currency = rk.measure.register_currency('AUD', registry=rk.measure.Index.registry)
print(currency)


# Next we define a `Flow` object from a list of dates and amounts:

# In[3]:


transactions = {
    pd.Timestamp('2020-01-01'): 100,
    pd.Timestamp('2020-01-02'): 200,
    pd.Timestamp('2019-01-01'): 300,
    pd.Timestamp('2020-12-31'): -100
    }

movements = pd.Series(data=transactions)

cash_flow = rk.flux.Flow(
    name='Operational Expenses',
    movements=movements,
    units=currency.units)

print('Flow:{0}{1}{0}{0}Flow Index:{0}{2}{0}'.format(
    os.linesep,
    cash_flow,
    cash_flow.movements.index,
    ))
cash_flow.movements.info()


# As you can see, a `Flow` has three properties:
# 1. it's Name,
# 2. a Pandas Series of date-stamped amounts ('Movements'), and
# 3. the units of the movement's amounts
# 
# * Note the following:
#     1. The movements can be in any (temporal) order,
#     2. The movements can be positive or negative,
#     3. The movements will be (or converted to) `float`s
#     4. The pd.Series index is a pd.DatetimeIndex

# ### Structuring a Table of Cash Flows
# Given a simple example of such a DCF valuation for a stylized commercial rental property, Rangekeeper provides enhanced functionality for constructing and structuring the proforma:

# ```{figure} resources/FaREVuU-table1.1.jpg
# ---
# width: 100%
# name: FaREVuU-table1.1
# ---
# Table 1.1 From {cite}`farevuu2018`
# ```
# 
# 
# ### A 'Span'
# `Span`s are used to define intervals of time that encompass the movements of a Flow.
# 
# A `Span` is a pd.Interval of pd.Timestamps that bound its start and end dates.
# 

# In[4]:


# Define a Span:
start_date = pd.Timestamp('2001-01-01')
num_periods = 11
span = rk.span.Span.from_num_periods(
    name='Operation',
    date=start_date,
    period_type=rk.periodicity.Type.YEAR,
    num_periods=num_periods)
print(span)


# ### A 'Projection'
# A `Projection` takes a value and casts it over a sequence of periods according to a specified logic. There are two classes of the form of the logic:
# 1. Extrapolation, which takes a starting value and from it generates a sequence of values over a sequence of dates, and
# 2. Distribution, which takes a total value and subdivides it over a sequence of dates.
# 
# To match the logic of line 4, 'Potential Gross Income', in Table 1.1 above, we will use a 'Compounding' Extrapolation:

# In[5]:


# Define a Compounding Projection:
compounding_rate = 0.02
projection = rk.projection.Extrapolation(
    form=rk.extrapolation.Compounding(rate=compounding_rate),
    sequence=span.to_index(period_type=rk.periodicity.Type.YEAR))


# Let's now use the previous definitions of `Flow`s and `Projection`s to construct the 'Potential Gross Income' line item:
# 

# In[6]:


# Define a compounding Cash Flow:
initial_income = 100 * currency.units
potential_gross_income = rk.flux.Flow.from_projection(
    name='Potential Gross Income',
    value=initial_income,
    proj=projection,
    units=currency.units)
potential_gross_income


# Similarly, we define the 'Vacancy' line item by multiplying the movements of the 'Potential Gross Income' `Flow` by a vacancy rate:

# In[7]:


vacancy_rate = 0.05
vacancy = rk.flux.Flow(
    name='Vacancy Allowance',
    movements=potential_gross_income.movements * -vacancy_rate,
    units=currency.units)
vacancy


# ```{note}
# Note the sign of the movements of the 'Vacancy Allowance' `Flow` -- it is negative, because it is an *outflow*.
# ```

# ## A 'Stream'
# A `Stream` is a collection of constituent `Flow`s into a table, such that their movements (transactions) are resampled with a specified periodicity.
# 
# Let's use the 'Effective Gross Income' line item in Table 1.1 to illustrate the concept of a `Stream`:

# In[8]:


effective_gross_income_stream = rk.flux.Stream(
    name='Effective Gross Income',
    flows=[potential_gross_income, vacancy],
    period_type=rk.periodicity.Type.YEAR)
effective_gross_income_stream


# As you can see, the `Stream` has a name, a table of constituent `Flow`s (each with their own units), with their movements resampled to the specified periodicity.
# 
# In order to aggregate the constituent `Flow`s, we can sum them into a resultant `Flow`:

# In[9]:


effective_gross_income_flow = effective_gross_income_stream.sum()
effective_gross_income_flow


# Note the `Flow`'s index is back to a `pd.DatetimeIndex`, with movements occuring at the *end* date of each period.

# With this in mind, we can complete Table 1.1

# In[10]:


opex_pgi_ratio = .35
operating_expenses = rk.flux.Flow(
    name='Operating Expenses',
    movements=potential_gross_income.movements * opex_pgi_ratio,
    units=currency.units).invert()

net_operating_income = rk.flux.Stream(
    name='Net Operating Income',
    flows=[effective_gross_income_flow, operating_expenses],
    period_type=rk.periodicity.Type.YEAR)

net_operating_income


# In[11]:


capex_pgi_ratio = .1
capital_expenditures = rk.flux.Flow(
    name='Capital Expenditures',
    movements=potential_gross_income.movements * capex_pgi_ratio,
    units=currency.units).invert()

net_annual_cashflows = rk.flux.Stream(
    name='Net Annual Cashflows',
    flows=[net_operating_income.sum(), capital_expenditures],
    period_type=rk.periodicity.Type.YEAR)

net_annual_cashflows


# To calculate the reversion cashflow, we set up a period that spans the 10th year of the project:

# In[12]:


reversion_span = rk.span.Span.from_num_periods(
    name='Reversion',
    date=start_date + pd.DateOffset(years=9),
    period_type=rk.periodicity.Type.YEAR,
    num_periods=1)

exit_caprate = 0.05
reversion_flow = rk.flux.Flow.from_projection(
    name='Reversion',
    value=net_annual_cashflows.sum().movements.values[-1] / exit_caprate,
    proj=rk.projection.Distribution(
        form=rk.distribution.Uniform(),
        sequence=reversion_span.to_index(period_type=rk.periodicity.Type.YEAR)),
    units=currency.units)
reversion_flow


# Finally, we can aggregate the net and reversion cashflows in order to calculate the project's complete cashflows:

# In[ ]:


net_cashflows_with_reversion = rk.flux.Stream(
    name='Net Cashflow with Reversion',
    flows=[net_annual_cashflows.sum(), reversion_flow],
    period_type=rk.periodicity.Type.YEAR).trim_to_span(
    rk.span.Span(
        start_date=start_date,
        end_date=reversion_span.end_date)
    )
net_cashflows_with_reversion


# Given that the discount rate is specified as 7%, we can calculate the project's Present Value (PV):

# In[ ]:


discount_rate = 0.07
pvs = net_cashflows_with_reversion.sum().pv(
    name='Present Value',
    period_type=rk.periodicity.Type.YEAR,
    discount_rate=discount_rate)
pvs


# In[ ]:


project_pv = pvs.collapse().movements.item()
round(project_pv, 2)


# In[ ]:




