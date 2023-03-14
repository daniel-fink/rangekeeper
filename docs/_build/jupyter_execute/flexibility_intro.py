#!/usr/bin/env python
# coding: utf-8

# # Introduction to Modeling Flexibility

# - Use the dynamics to simulate multiple potential outcomes of the proforma.

# In[1]:


import pandas as pd

import rangekeeper as rk


# In[32]:


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
    'discount_rate': 0.07
    }


# In[33]:


class TraditionalModel:
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
        self.reversion_span = self.span.shift(
            name='Reversion Span',
            num_periods=9,
            period_type=params['period_type'],
            bound='start')

        self.acquisition = rk.flux.Flow.from_projection(
            name='Acquisition',
            value=params['acquisition_cost'],
            proj=rk.projection.Distribution(
                form=rk.distribution.Uniform(),
                sequence=self.acq_span.to_index(period_type=params['period_type'])),
            units=currency.units)

        self.pgi = rk.flux.Flow.from_projection(
            name='Potential Gross Income',
            value=params['initial_income'],
            proj=rk.projection.Extrapolation(
            form=rk.extrapolation.Compounding(
                rate=params['growth_rate']),
            sequence=self.calc_span.to_index(period_type=params['period_type'])),
            units=currency.units)
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

        self.pbtcfs = rk.flux.Stream(
            name='PBTCFs',
            flows=[
                self.net_cfs.trim_to_span(span=self.span),
                self.reversions.trim_to_span(span=self.reversion_span)
                ],
            period_type=params['period_type'])

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
trad_model = TraditionalModel(params)


# In[ ]:





# This notebook models Chapter 9 of {cite}`farevuu2018. It expands the possible time horizon considered in the basic, linear, deterministic DCF model, in order to explore fully the general case of resale timing. For this analysis, the traditional DCF model extends the number of future years from a 10‐year horizon to a much larger number-- 24 years. It also allows the model to represent a resale before the horizon of the analysis, if a 'stop-gain' rule is triggered. A 'stop-gain' rule specifies the sale of the asset as soon as its price rises above a pre‐specified (trigger) level, no matter what, and not to sell the asset before then.
# 
# The methodology behind the flexibility of the 'stop-gain' rule is the use of conditional ("if") statements to specify the control flow of the program (DCF analysis). Conditional statements are commands that trigger a decision when the program encounters pre‐specified conditions. They provide the means to automate
# the process of mimicking the decisions that investors or managers would take.

# ### Modeling a flexible resale-timing DCF

# In[37]:


trad_model.irrs.movements[-1]


# In[34]:




