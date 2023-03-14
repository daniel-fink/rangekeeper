#!/usr/bin/env python
# coding: utf-8

# # Deterministic Scenario Analysis
# This document showcases how `Rangekeeper` can easily produce alternate model versions (scenarios)

# Given the original deterministic proforma (Table 1.1):

# In[1]:


import pandas as pd
import pint
import rangekeeper as rk


# ## Set up the proforma to accept a dictionary of input parameters:
# In order to quickly create alternate scenarios, we can create a class function that takes a dictionary of parameters as input. This allows us to easily create alternate scenarios by simply changing the parameters in the dictionary.

# ### Set up proforma parameters:

# In[44]:


currency = rk.measure.register_currency('USD', registry=rk.measure.Index.registry)
params = {
    'start_date': pd.Timestamp('2001-01-01'),
    'num_periods': 10,
    'period_type': rk.periodicity.Type.YEAR,
    'acquisition_cost': -1000 * currency.units,
    'initial_income': 100 * currency.units,
    'growth_rate': 0.02,
    'vacancy_rate': 0.05,
    'opex_pgi_ratio': 0.35,
    'capex_pgi_ratio': 0.1,
    'exit_caprate': 0.05,
    'discount_rate': 0.07,

    # Table 4.1 has proformas that absorb an additional straight-line income flow:
    'addl_pgi_init': 0,
    'addl_pgi_slope': 0,
    }


# In[45]:


class Model:
    def __init__(self, params: dict):
        self.calc_span = rk.span.Span.from_num_periods(
            name='Span to Calculate Reversion',
            date=params['start_date'],
            period_type=params['period_type'],
            num_periods=params['num_periods'] + 1)
        self.acq_span = rk.span.Span.from_num_periods(
            name='Acquisition Span',
            date=rk.periodicity.date_offset(
                params['start_date'],
                num_periods=-1,
                period_type=params['period_type']),
            period_type=params['period_type'],
            num_periods=1)
        self.span = self.calc_span.shift(
            name='Span',
            num_periods=-1,
            period_type=params['period_type'],
            bound='end')

        self.acquisition = rk.flux.Flow.from_projection(
            name='Acquisition',
            value=params['acquisition_cost'],
            proj=rk.projection.Distribution(
                form=rk.distribution.Uniform(),
                sequence=self.acq_span.to_index(period_type=params['period_type'])),
            units=currency.units)

        self.base_pgi = rk.flux.Flow.from_projection(
            name='Base Potential Gross Income',
            value=params['initial_income'],
            proj=rk.projection.Extrapolation(
            form=rk.extrapolation.Compounding(
                rate=params['growth_rate']),
            sequence=self.calc_span.to_index(period_type=params['period_type'])),
            units=currency.units)

        # Table 4.1 has proformas that absorb an additional straight-line income flow
        self.addl_pgi = rk.flux.Flow.from_projection(
            name='Additional Potential Gross Income',
            value=params['addl_pgi_init'],
            proj=rk.projection.Extrapolation(
                form=rk.extrapolation.StraightLine(
                    slope=params['addl_pgi_slope']),
                sequence=self.calc_span.to_index(period_type=params['period_type'])),
            units=currency.units)

        self.pgi = rk.flux.Stream(
            name='Potential Gross Income',
            flows=[self.base_pgi, self.addl_pgi],
            period_type=params['period_type']).sum()

        self.vacancy = rk.flux.Flow(
            name='Vacancy Allowance',
            movements=self.pgi.movements * -params['vacancy_rate'],
            units=currency.units)
        self.egi = rk.flux.Stream(
            name='Effective Gross Income',
            flows=[self.pgi, self.vacancy],
            period_type=params['period_type']).sum()
        self.opex = rk.flux.Flow(
            name='Operating Expenses',
            movements=self.pgi.movements * params['opex_pgi_ratio'],
            units=currency.units).invert()
        self.noi = rk.flux.Stream(
            name='Net Operating Income',
            flows=[self.egi, self.opex],
            period_type=params['period_type']).sum()
        self.capex = rk.flux.Flow(
            name='Capital Expenditures',
            movements=self.pgi.movements * params['capex_pgi_ratio'],
            units=currency.units).invert()
        self.net_cfs = rk.flux.Stream(
            name='Net Annual Cashflows',
            flows=[self.noi, self.capex],
            period_type=params['period_type']).sum()

        self.reversions = rk.flux.Flow(
            name='Reversions',
            movements=self.net_cfs.movements.shift(periods=-1).dropna() / params['exit_caprate'],
            units=currency.units).trim_to_span(span=self.span)
        self.net_cfs = self.net_cfs.trim_to_span(span=self.span)

        pvs = []
        irrs = []
        for period in self.net_cfs.movements.index:
            cumulative_net_cfs = self.net_cfs.trim_to_span(
                span=rk.span.Span(
                    name='Cumulative Net Cashflow Span',
                    start_date=params['start_date'],
                    end_date=period))
            reversion = rk.flux.Flow(
                movements=self.reversions.movements.loc[[period]],
                units=currency.units)
            cumulative_net_cfs_with_rev = rk.flux.Stream(
                name='Net Cashflow with Reversion',
                flows=[cumulative_net_cfs, reversion],
                period_type=params['period_type'])
            pv = cumulative_net_cfs_with_rev.sum().pv(
                name='Present Value',
                period_type=params['period_type'],
                discount_rate=params['discount_rate'])
            pvs.append(pv.collapse().movements)

            incl_acq = rk.flux.Stream(
                name='Net Cashflow with Reversion and Acquisition',
                flows=[cumulative_net_cfs_with_rev.sum(), self.acquisition],
                period_type=params['period_type'])

            irrs.append(round(incl_acq.sum().xirr(), 4))

        self.pvs = rk.flux.Flow(
            name='Present Values',
            movements=pd.concat(pvs),
            units=currency.units)
        self.irrs = rk.flux.Flow(
            name='Internal Rates of Return',
            movements=pd.Series(irrs, index=self.pvs.movements.index),
            units=None)


# In[46]:


model = Model(params)
model.pvs
model.irrs


# We can now create the 'Panel B' (Optimistic) scenario as documented in Table 4.1:

# ```{figure} resources/FaREVuU-table4.1.png
# ---
# width: 100%
# name: FaREVuU-table4.1
# ---
# Table 4.1 From Geltner & De Neufville, 2018
# ```

# In[1]:


optimistic_params = params.copy()
optimistic_params['initial_income'] = params['initial_income'] + 10 * currency.units
optimistic_params['addl_pgi_slope'] = 3

optimistic = Model(optimistic_params)
print(optimistic.pvs)
print(optimistic.irrs)


# Similarly, we can create the 'Panel C' (Pessimistic) scenario:

# In[48]:


pessimistic_params = params.copy()
pessimistic_params['initial_income'] = params['initial_income'] - 10 * currency.units
pessimistic_params['addl_pgi_slope'] = -3

pessimistic = Model(pessimistic_params)
pessimistic.pvs
pessimistic.irrs


# Given that both scenarios have a 50% chance of occuring, the EV (Expected Value) at each time period is:

# In[49]:


evs = (optimistic.pvs.movements + pessimistic.pvs.movements) / 2
print(evs)


# And the expected return (IRR) at each time period is:

# In[50]:


ers = (optimistic.irrs.movements + pessimistic.irrs.movements) / 2
print(ers)


# Continuing with de Neufville & Geltner (2018)'s chapter 4.3, we can calculate the value of the flexibility, assuming it is possible to sell the property at will:

# In[54]:


value_of_flex = (optimistic.pvs.movements[-1] / 2 + pessimistic.pvs.movements[0] / 2) - evs[-1]
print(value_of_flex)


# In[ ]:




