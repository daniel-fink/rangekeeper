import pandas as pd
import numpy_financial
from typing import Dict
import datetime
import aenum

import modules.distribution
import modules.flux
from modules.space import Apartment
from modules.units import Units
from modules.periodicity import Periodicity
from modules.distribution import DistributionType


# Phasing:
def compose_phases(project_params: Dict):
    """
    Inserts phasing params into the project params.

    :param project_params: A dictionary with the following entries:
    start_date: pd.Timestamp,
    periodicity_type: Periodicity.Type,
    preliminaries_duration: int,
    construction_duration: int,
    sales_duration: int,
    sales_fee_rate: float,
    construction_interest_rate_pa: float,
    parking_ratio: float,
    units: Units.Type,
    margin_on_cost_reqd: float
    """

    project_params['preliminaries_period'] = Periodicity.period_sequence(
        include_start=project_params['start_date'],
        include_end=Periodicity.date_offset(date=project_params['start_date'],
                                            period_type=project_params['periodicity_type'],
                                            number=project_params['preliminaries_duration'] - 1),
        periodicity=project_params['periodicity_type'])

    construction_start_date = Periodicity.date_offset(
        date=project_params['preliminaries_period'].end_time[-1].date(),
        period_type=Periodicity.Type.day,
        number=1)

    project_params['construction_period'] = Periodicity.period_sequence(
        include_start=construction_start_date,
        include_end=Periodicity.date_offset(date=construction_start_date,
                                            period_type=project_params['periodicity_type'],
                                            number=project_params['construction_duration'] - 1),
        periodicity=project_params['periodicity_type'])

    sales_start_date = Periodicity.date_offset(
        date=project_params['construction_period'].end_time[-1].date(),
        period_type=Periodicity.Type.day,
        number=1)

    project_params['sales_period'] = Periodicity.period_sequence(
        include_start=sales_start_date,
        include_end=Periodicity.date_offset(date=sales_start_date,
                                            period_type=project_params['periodicity_type'],
                                            number=project_params['sales_duration'] - 1),
        periodicity=project_params['periodicity_type'])


# Apartments:
def compose_apartments(unit_mix: Dict, project_params: Dict):
    gfa = []
    cfa_amenities = []
    cfa_shell = []
    apartments = []
    for key, value in unit_mix.items():
        if value > 0:
            apartment = modules.space.Apartment.from_type(apartment_type=key)
            for i in range(0, value):
                gfa.append(apartment.gfa)
                cfa_amenities.append(apartment.cfa_amenities)
                cfa_shell.append(apartment.cfa_shell)
                apartments.append(apartment)

    project_params['gfa'] = sum(gfa)
    project_params['cfa_amenities'] = sum(cfa_amenities)
    project_params['cfa_shell'] = sum(cfa_shell)
    project_params['apartments'] = apartments


# Preliminaries Costs:
def compose_prelim_costs(
        preliminaries_costs_index: Dict,
        project_params: Dict):
    """
        :param preliminaries_costs_index: A dictionary with the following entries:
        design_planning_engineering_cost: float,
        survey_geotech_cost: float,
        permitting_inspections_certifications_cost: float,
        legal_title_appraisal_cost: float,
        taxes_insurance_cost: float,
        developer_project_management_cost: float,

        :param project_params: A dictionary with the following entries:
        start_date: pd.Timestamp,
        preliminaries_duration: int,
        construction_duration: int,
        construction_interest_rate_pa: float,
        gfa_shell: float,
        gfa_cores: float,
        gla: float,
        num_parking_stalls: int,
        periodicity_type: Periodicity.Type,
        units: Units.Type,

        :return: A Confluence of preliminary cost Flows
        """

    designplanningengineering_flow = modules.flux.Flow.from_total(
        name='design_planning_engineering',
        total=preliminaries_costs_index['design_planning_engineering_cost'],
        index=project_params['preliminaries_period'],
        distribution=modules.distribution.Uniform(),
        units=project_params['units'])

    surveygeotech_flow = modules.flux.Flow.from_total(
        name='survey_geotech',
        total=preliminaries_costs_index['survey_geotech_cost'],
        index=project_params['preliminaries_period'],
        distribution=modules.distribution.Uniform(),
        units=project_params['units'])

    permittinginspectionscertifications_flow = modules.flux.Flow.from_total(
        name='permitting_inspections_certifications',
        total=preliminaries_costs_index['permitting_inspections_certifications_cost'],
        index=project_params['preliminaries_period'],
        distribution=modules.distribution.Uniform(),
        units=project_params['units'])

    legaltitleappraisal_flow = modules.flux.Flow.from_total(
        name='legal_title_appraisal',
        total=preliminaries_costs_index['legal_title_appraisal_cost'],
        index=project_params['preliminaries_period'],
        distribution=modules.distribution.Uniform(),
        units=project_params['units'])

    taxesinsurance_flow = modules.flux.Flow.from_total(
        name='taxes_insurance',
        total=preliminaries_costs_index['taxes_insurance_cost'],
        index=project_params['preliminaries_period'],
        distribution=modules.distribution.Uniform(),
        units=project_params['units'])

    developerprojectmanagement_flow = modules.flux.Flow.from_total(
        name='developer_project_management',
        total=preliminaries_costs_index['developer_project_management_cost'],
        index=project_params['preliminaries_period'],
        distribution=modules.distribution.Uniform(),
        units=project_params['units'])

    preliminaries_costs = modules.flux.Confluence(
        name='preliminaries_costs',
        affluents=[designplanningengineering_flow,
                   surveygeotech_flow,
                   permittinginspectionscertifications_flow,
                   legaltitleappraisal_flow,
                   taxesinsurance_flow,
                   developerprojectmanagement_flow],
        periodicity_type=project_params['periodicity_type'])

    return preliminaries_costs


# Building Construction Costs:
def compose_build_costs(
        build_costs_index: Dict,
        property_params: Dict,
        project_params: Dict):
    """

    :param property_params:
    :param build_costs_index: A dictionary with the following entries:
    construction_cost_shell_pergfa: float,
    construction_cost_cores_pergfa: float,
    siteworks_cost_pergla: float,
    parking_cost_per_stall: float,
    utilities_cost: float

    :param project_params: A dictionary with the following entries:
    start_date: pd.Timestamp,
    preliminaries_duration: int,
    construction_duration: int,
    construction_interest_rate_pa: float,
    gfa_shell: float,
    gfa_cores: float,
    gla: float,
    num_parking_stalls: int,
    periodicity_type: Periodicity.Type,
    units: Units.Type

    :return:
    """

    construction_shell_flow = modules.flux.Flow.from_total(
        name='construction_shell',
        total=project_params['cfa_shell'] * build_costs_index['construction_cost_shell_pergfa'],
        index=project_params['construction_period'],
        distribution=modules.distribution.PERT(peak=0.75, weighting=4),
        units=project_params['units'])

    construction_cores_flow = modules.flux.Flow.from_total(
        name='construction_cores',
        total=project_params['cfa_amenities'] * build_costs_index['construction_cost_cores_pergfa'],
        index=project_params['construction_period'],
        distribution=modules.distribution.PERT(peak=0.33, weighting=4),
        units=project_params['units'])

    siteworks_flow = modules.flux.Flow.from_total(
        name='siteworks',
        total=property_params['gla'] * build_costs_index['siteworks_cost_pergla'],
        index=project_params['construction_period'],
        distribution=modules.distribution.PERT(peak=0.25, weighting=4),
        units=project_params['units'])

    parking_flow = modules.flux.Flow.from_total(
        name='parking',
        total=project_params['parking_ratio'] * len(project_params['apartments']) * build_costs_index['parking_cost_per_stall'],
        index=project_params['construction_period'],
        distribution=modules.distribution.PERT(peak=0.75, weighting=4),
        units=project_params['units'])

    utilities_flow = modules.flux.Flow.from_total(
        name='utilities',
        total=build_costs_index['utilities_cost'],
        index=project_params['construction_period'],
        distribution=modules.distribution.Uniform(),
        units=project_params['units'])

    build_costs = modules.flux.Confluence(
        name='build_costs',
        affluents=[construction_shell_flow,
                   construction_cores_flow,
                   siteworks_flow,
                   parking_flow,
                   utilities_flow],
        periodicity_type=project_params['periodicity_type'])

    return build_costs


# Financing Costs:
def compose_finance_costs(  # TODO: Add fees and remove loan_drawdown, loan_balance...
        project_params: Dict,
        preliminaries_costs: modules.flux.Confluence,
        build_costs: modules.flux.Confluence):
    """

    :param project_params:
    :param preliminaries_costs:
    :param build_costs:
    :return:
    """

    loan_confluence = modules.flux.Confluence(
        name='loan',
        affluents=[preliminaries_costs.sum(), build_costs.sum()],
        periodicity_type=project_params['periodicity_type'])

    interest_rate_per_period = project_params['construction_interest_rate_pa'] / Periodicity.periods_per_year(project_params['periodicity_type'])
    loan_drawdown = loan_confluence.sum(name='loan_drawdown')

    interest = []
    loan_balance = []
    for i in range(0, loan_drawdown.movements.size):
        if i == 0:
            previous_balance = 0
        else:
            previous_balance = loan_balance[i - 1]
        current_balance = previous_balance + loan_drawdown.movements.iloc[i].item()
        interest.append(current_balance * interest_rate_per_period)
        loan_balance.append(current_balance + interest[i])

    interest = modules.flux.Flow.from_periods(
        name='interest',
        periods=loan_confluence.confluence.index.to_period(),
        data=interest,
        units=project_params['units'])

    loan_balance = modules.flux.Flow.from_periods(
        name='loan_balance',
        periods=loan_confluence.confluence.index.to_period(),
        data=loan_balance,
        units=project_params['units'])

    construction_finance_confluence = modules.flux.Confluence(
        name='construction_financing',
        affluents=[loan_drawdown, loan_balance, interest],
        periodicity_type=project_params['periodicity_type'])

    return construction_finance_confluence


# Revenues:
def compose_revenues(
        project_params: Dict,
        property_params: Dict,
        ):
    """

    :param property_params:
    :param revenues_index:
    :param project_params:
    :return:
    """

    revenues_flow = modules.flux.Flow.from_total(
        name='sales',
        total=project_params['gfa'] * property_params['sales_price_per_gfa'],
        index=project_params['sales_period'],
        distribution=modules.distribution.PERT(peak=0.5, weighting=4),
        units=project_params['units'])

    sales_fee_flow = modules.flux.Flow(
        name='sales_fee',
        movements=revenues_flow.movements.multiply(project_params['sales_fee_rate']),
        units=project_params['units'])

    revenues = modules.flux.Confluence(
        name='revenues',
        affluents=[revenues_flow, sales_fee_flow.invert()],
        periodicity_type=project_params['periodicity_type'])

    return revenues

# Metrics:
def calculate_development_metrics(
        unit_mix: Dict,
        project_params: Dict,
        property_params: Dict,
        preliminary_costs_index: Dict,
        build_costs_index: Dict
        ):
    """

    :param property_params:
    :param unit_mix:
    :param project_params:
    :param preliminary_costs_index:
    :param build_costs_index:
    :return:
    """

    # Extend Project Params
    modules.model.compose_phases(project_params)
    modules.model.compose_apartments(
        unit_mix=unit_mix,
        project_params=project_params)

    # Preliminaries:
    preliminaries = modules.model.compose_prelim_costs(
        preliminaries_costs_index=preliminary_costs_index,
        project_params=project_params)

    # Build Costs
    build_costs = modules.model.compose_build_costs(
        build_costs_index=build_costs_index,
        property_params=property_params,
        project_params=project_params)

    # Finance Costs:
    finance_costs = modules.model.compose_finance_costs(
        project_params=project_params,
        preliminaries_costs=preliminaries,
        build_costs=build_costs)

    interest_costs = finance_costs.extract('interest')

    # Net Development Cost:
    net_development_costs = modules.flux.Confluence.merge(
        confluences=[
            preliminaries,
            build_costs,
            interest_costs.to_confluence(periodicity_type=project_params['periodicity_type'])
            ],
        name='net_development_costs',
        periodicity_type=project_params['periodicity_type'])

    # Revenues:
    revenues = modules.model.compose_revenues(
        project_params=project_params,
        property_params=property_params)

    # Net Development Revenue:
    ndr_confluence = modules.flux.Confluence(
        name='net_development_revenue',
        affluents=[net_development_costs.sum().invert(), revenues.sum()],
        periodicity_type=project_params['periodicity_type'])
    net_development_revenue = ndr_confluence.sum()

    # Metrics:
    margin = (project_params['margin_on_cost_reqd'] * net_development_costs.collapse().sum().movements)[0]
    residual_land_value = net_development_revenue.sum().movements[0] - margin

    investment_flow = modules.flux.Flow.from_dict(
        name='investment',
        movements={project_params['start_date']: (-1) * residual_land_value},
        units=project_params['units'])
    ndr_confluence.append(affluents=[investment_flow])

    net_development_flow = ndr_confluence.sum()
    irr = net_development_flow.xirr()

    return pd.Series(
        data={
            'preliminaries_total': preliminaries.collapse().sum().movements.iloc[0],
            'build_costs_total': build_costs.collapse().sum().movements.iloc[0],
            'finance_costs_total': interest_costs.sum().movements.iloc[0],
            'net_development_costs': net_development_costs.collapse().sum().movements.iloc[0],
            'revenues': revenues.collapse().sum().movements.iloc[0],
            'net_development_revenue': net_development_revenue.sum().movements.iloc[0],
            'gfa': project_params['gfa'],
            'effective_far': project_params['gfa'] / property_params['gla'],
            'residual_land_value': residual_land_value,
            'project_irr': irr
            }
        )