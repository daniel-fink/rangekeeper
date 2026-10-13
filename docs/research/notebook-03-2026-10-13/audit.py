"""Independent CSV arithmetic, evaluated after the chapter in its fresh kernel."""
import csv
import importlib.metadata
from pathlib import Path

rows = list(csv.DictReader((package / 'inventory.csv').open()))
csv_floors = [r for r in rows if r['classification'] == 'floor']
csv_utilities = [r for r in rows if r['classification'] == 'utilities' and r['volume_m3']]
phase_lookup = {source_model.entity(UUID(p['object_id'])).name: p for p in plan['phases']}
hard_expected = {branch: sum(float(r['gfa_m2']) * plan['construction_AUD_per_m2'][r['effective_use']]
                    for r in csv_floors if r['branch'] == branch) for branch in phase_lookup}
budget_expected = {branch: hard * (1 + plan['soft_cost_fraction_of_hard_cost'] + plan['contingency_fraction_of_hard_cost'])
                   for branch, hard in hard_expected.items()}
timeline_expected = {}
for year in range(2027, 2038):
    income = expense = replacements = build = 0.0
    for r in csv_floors:
        inputs = legacy['use_assumptions'][r['effective_use']]
        opening = int(phase_lookup[r['branch']]['open'][:4])
        if year >= opening:
            income += float(r['gfa_m2']) * inputs['efficiency'] * inputs['initial_rent_AUD_per_m2_per_year'] * (1-inputs['vacancy']) * (1+inputs['annual_income_growth']) ** (year-2027)
            expense += (float(r['gfa_m2']) * inputs['floor_opex_AUD_per_m2_per_year'] + float(r['perimeter_m']) * float(r['ftf_m']) * inputs['facade_opex_AUD_per_m2_per_year']) * (1+legacy['annual_opex_growth']) ** (year-2027)
            age = year-opening+1
            if age % 5 == 0:
                replacements += float(r['gfa_m2']) * inputs['floor_capex_AUD_per_m2_per_payment'] * (1.035 ** (age//5-1))
    for r in csv_utilities:
        age = year-int(phase_lookup[r['branch']]['open'][:4])+1
        if age > 0 and age % 5 == 0:
            replacements += float(r['volume_m3']) * legacy['utility_capex_AUD_per_m3_per_payment'][r['effective_use']] * (1.035 ** (age//5-1))
    for branch,p in phase_lookup.items():
        for payment_year,weight in zip(p['payment_years'],p['payment_weights']):
            if payment_year==year: build -= budget_expected[branch]*weight
    timeline_expected[year] = dict(egi=income,opex=expense,renewal=replacements,construction=build)
    for metric,flow in [('egi',egi),('opex',opex),('renewal',renewal),('construction',construction)]:
        assert math.isclose(flow.movements[year-2027].number,timeline_expected[year][metric],rel_tol=1e-10,abs_tol=1e-6), (year,metric)
end_nacf = sum(timeline_expected[2037][key] for key in ['egi','opex','renewal'])
terminal = end_nacf / plan['valuation']['exit_capitalization_rate']
expected_npv = -plan['land_cost_AUD'] + sum(
    (sum(timeline_expected[year].values()) + (terminal if year == 2036 else 0)) / (1+plan['valuation']['annual_discount_rate']) ** (year-2026)
    for year in range(2027,2037))
assert math.isclose(project_npv,expected_npv,rel_tol=1e-10,abs_tol=1e-6)
l = plan['lending']; rate = l['nominal_annual_mortgage_rate']/l['payments_per_year']
constant = l['payments_per_year']*rate/(1-(1+rate)**(-l['payments_per_year']*l['amortization_years']))
coefficient = l['leverage']*constant*l['coverage']
cost = sum(budget_expected.values()) + plan['construction_finance_allowance_AUD']
ref = timeline_expected[2032]
expected_factor = (coefficient*(plan['land_cost_AUD']+cost)-ref['opex'])/ref['egi']
expected_land = (ref['egi']+ref['opex'])/coefficient-cost
assert math.isclose(required_factor,expected_factor,rel_tol=1e-9)
assert math.isclose(supportable_land,expected_land,rel_tol=1e-9)
balance = plan['funding']['equity_AUD']-plan['land_cost_AUD']
remaining = plan['funding']['bridge_limit_AUD']
for row in funding_rows:
    year = row['Year']; draw = plan['funding']['draws_AUD_by_year'][str(year)]
    remaining -= draw
    balance += draw + sum(timeline_expected[year].values()) - (plan['construction_finance_allowance_AUD'] if year==2031 else 0)
    assert math.isclose(row['Closing cash'],balance,abs_tol=1e-6)
    assert math.isclose(row['Undrawn facility'],remaining,abs_tol=1e-6)
assert first_payment < committed_resources < remaining_obligations
assert project_npv > 0 and peak_shortfall > 0
assert required_factor < 1 and supportable_land > land_cost
assert model.system.relationships == source_model.system.relationships
assert model.system.entities == source_model.system.entities
for entity in whole_view.entities:
    assert front_model.entity(entity.id).name == entity.name
    assert back_model.entity(entity.id).name == entity.name
    for v in entity.characteristics.values or ():
        assert front_model.value(v.id) == v and back_model.value(v.id) == v
assert codec.dumps(source_model)==source_before
assert front_spec.record.model == back_spec.record.model == model.id
front_fixed = {a.target.target for a in front_spec.record.assignments}
back_fixed = {a.target.target for a in back_spec.record.assignments}
assert front_fixed ^ back_fixed == {value_ids['land_cost'],value_ids['rent_factor']}
assert front_model.system.formulations == back_model.system.formulations == model.system.formulations
diagnostics = {name: {'completion':r.report.status.completion.value,'solution':r.report.status.solution.value,
                     'codes':sorted({d.code for d in r.report.diagnostics})} for name,r in diagnostic_runs.items()}
assert diagnostics['Land and rent both unknown']['solution']=='feasible'
assert diagnostics['Incompatible fixed pair']['solution']=='infeasible'
assert diagnostics['Unknown leverage × cost']['completion']=='failed'
print(json.dumps({'results':results,'source_objects':len(whole_view.entities),'floors':len(csv_floors),
    'renewal_contributors':len(csv_floors)+len(csv_utilities),'construction_cost':construction_cost,
    'first_B_payment':first_payment,'committed_resources':committed_resources,
    'remaining_obligations':remaining_obligations,'diagnostics':diagnostics,
    'checks':['Independent inventory arithmetic for every annual flow','Land at t=0, annual PV and terminal forecast',
              'SFFA forward and inverse against closed forms','Funding balances and remaining commitments',
              'All physical identities and Values preserved','Same relations and Model pin; two role changes'],
    'versions':{name:importlib.metadata.version(name) for name in ['rangekeeper','plotly','polars','nbclient','jupyter-book']}
},indent=2))
