import math
import pandas as pd
import numpy_financial as npf

import modules.distribution
from modules.flux import Flow, Aggregation
from modules.units import Units
from modules.periodicity import Periodicity
from modules.distribution import Type, Uniform, Exponential
from modules.phase import Phase

# Setup:
units = Units.Type.USD

# Phasing:
acquisition_phase = Phase.from_num_periods(name='Acquisition',
                                           start_date=pd.Timestamp(2020, 1, 1),
                                           period_type=Periodicity.Type.year,
                                           num_periods=1)

operation_phase = Phase.from_num_periods(name='Operation',
                                         start_date=Periodicity.date_offset(date=acquisition_phase.end_date,
                                                                            period_type=Periodicity.Type.day,
                                                                            num_periods=1),
                                         period_type=Periodicity.Type.year,
                                         num_periods=10)

projection_phase = Phase.from_num_periods(name='Projection',
                                          start_date=Periodicity.date_offset(date=operation_phase.end_date,
                                                                             period_type=Periodicity.Type.day,
                                                                             num_periods=1),
                                          period_type=Periodicity.Type.year,
                                          num_periods=1)

noi_calc_phase = Phase.merge(name='NOI Calculation Phase',
                             phases=[operation_phase, projection_phase])

reversion_phase = Phase.from_num_periods(name='Reversion',
                                         start_date=pd.Timestamp(2030, 1, 1),
                                         period_type=Periodicity.Type.year,
                                         num_periods=1)

# Cashflows:
period_type = Periodicity.Type.year
growth_rate = 0.02
distribution = modules.distribution.Exponential(rate=growth_rate,
                                                num_periods=noi_calc_phase.duration(period_type=period_type,
                                                                                    inclusive=True))

# Potential Gross Income
pgi = Flow.from_initial(name='Potential Gross Income',
                        initial=100.,
                        index=noi_calc_phase.to_index(periodicity=period_type),
                        distribution=Exponential(rate=growth_rate,
                                                 num_periods=noi_calc_phase.duration(period_type=period_type,
                                                                                     inclusive=True)),
                        units=units)

# Vacancy Allowance
vacancy_rate = 0.05
vacancy = Flow.from_periods(name='Vacancy Allowance',
                            periods=noi_calc_phase.to_index(periodicity=period_type),
                            data=pgi.movements * vacancy_rate,
                            units=units).invert()

# Effective Gross Income:
egi = Aggregation(name='Effective Gross Income',
                  aggregands=[pgi, vacancy],
                  periodicity_type=period_type)

# Operating Expenses:
opex_pgi_ratio = 0.35
opex = Flow.from_periods(name='Operating Expenses',
                         periods=noi_calc_phase.to_index(periodicity=period_type),
                         data=pgi.movements * opex_pgi_ratio,
                         units=units).invert()

# Net Operating Income:
noi = Aggregation(name='Net Operating Income',
                  aggregands=[egi.sum('Effective Gross Income'), opex],
                  periodicity_type=period_type)

# Capital Expenses:
capex_pgi_ratio = 0.10
capex = Flow.from_periods(name='Capital Expenses',
                          periods=noi_calc_phase.to_index(periodicity=period_type),
                          data=pgi.movements * capex_pgi_ratio,
                          units=units).invert()

# Net Cashflows:
ncf = Aggregation(name='Net Cashflows',
                  aggregands=[noi.sum(), capex],
                  periodicity_type=period_type)

# Reversion:
cap_rate = 0.05
sale_value = ncf.sum().movements.tail(1).item() / cap_rate
reversion = Flow.from_periods(name='Reversion',
                              periods=reversion_phase.to_index(periodicity=period_type),
                              data=[sale_value],
                              units=units)

# Add Reversion to NCFs
ncf.append(aggregands=[reversion])
ncf_operating = Aggregation.from_DataFrame(name='Operating Net Cashflows',
                                           data=ncf.aggregation.truncate(after=operation_phase.end_date, copy=True),
                                           units=units)

# Calculate the Present Value of the NCFs
discount_rate = 0.07

pv_ncf_operating = ncf_operating.sum().movements.to_frame()
pv_ncf_operating.insert(0, 'index', range(ncf_operating.aggregation.index.size))
pv_ncf_operating['Discounted Net Cashflows'] = pv_ncf_operating.apply(
    lambda movement: movement['Operating Net Cashflows'] / math.pow((1 + discount_rate), movement['index'] + 1), axis=1)
pv_ncf_operating.drop(columns=['index'], inplace=True)
# npv_ncf_operating = npf.npv(discount_rate, ncf_operating.sum().movements)
