import csv, sys, hashlib
from importlib.metadata import version
rows = list(csv.DictReader((package / 'inventory.csv').open()))
reference = {'egi': [0.0]*11, 'opex':[0.0]*11, 'capex':[0.0]*11}
for row in rows:
    if row['classification'] == 'floor':
        a = use_inputs[row['effective_use']]
        area = float(row['gfa_m2'])
        facade = float(row['perimeter_m']) * float(row['ftf_m'])
        rent = area*a['efficiency']*a['initial_rent_AUD_per_m2_per_year']*(1-a['vacancy'])
        cost = area*a['floor_opex_AUD_per_m2_per_year'] + facade*a['facade_opex_AUD_per_m2_per_year']
        for year in range(11):
            reference['egi'][year] += rent*(1+a['annual_income_growth'])**year
            reference['opex'][year] += cost*(1+assumptions['annual_opex_growth'])**year
        capital = area*a['floor_capex_AUD_per_m2_per_payment']
    elif row['effective_use'] in ('plant','cores'):
        capital = float(row['volume_m3'])*utility_rates[row['effective_use']]
    else:
        continue
    for payment in capital_payments:
        index = date.fromisoformat(payment['date']).year - 2001
        reference['capex'][index] += capital*(1+assumptions['capex_growth_per_payment_interval'])**payment['growth_exponent']
for metric, flow in [('egi',property_egi),('opex',property_opex),('capex',property_capex)]:
    assert len(flow.movements)==11
    assert all(math.isclose(m.number, expected,rel_tol=1e-12,abs_tol=1e-6) for m,expected in zip(flow.movements,reference[metric])), metric
reference_nacf = [sum(reference[metric][i] for metric in reference) for i in range(11)]
reference_pv = sum((reference_nacf[i] + (reference_nacf[10]/exit_rate if i==9 else 0))/(1+discount_rate)**(i+1) for i in range(10))
assert math.isclose(reference_pv,manual_pv,rel_tol=1e-12)
assert math.isclose(sum(value_nacf(flow) for flow in nacf_by_branch.values()),manual_pv,rel_tol=1e-12)
assert math.isclose(sum(value_nacf(flow) for flow in variant_nacf_by_branch.values()),value_nacf(variant_property_nacf),rel_tol=1e-12)
# Explicit check of NOI + all intended capital contributions, every period.
assert all(math.isclose(noi.number+cap.number,nacf.number,abs_tol=1e-7) for noi,cap,nacf in zip(property_noi.movements,property_capex.movements,property_nacf.movements))
import rangekeeper
print(json.dumps({
 'python':sys.version,'rangekeeper_file':rangekeeper.__file__,
 'versions':{name:version(name) for name in ['rangekeeper','polars','plotly','pyvis','nbclient','jupyter-book']},
 'counts':{'objects':len(whole_view.entities),'relationships':len(whole_view.relationships),'floors':len(floors),'physical_utilities':len(utilities),'capex_contributors':len(capex_by_component),'changed_residential_floors':len(changed_ids)},
 'gfa_m2':gfa.root_value.magnitude,
 'first_egi':property_egi.movements[0].number,
 'first_opex':property_opex.movements[0].number,
 'first_capex_payment':sum(first_capex.values()),
 'sale_value':sale_value, 'reference_asset_value':manual_pv,
 'independent_asset_value':reference_pv, 'variant_asset_value':value_nacf(variant_property_nacf),
 'comparison':comparison.to_dicts(), 'source_model_unchanged':codec.dumps(model)==source_before,
 'checks':['independent CSV arithmetic for all 11 annual EGI/OPEX/CAPEX values','36 unique contributors','NOI + CAPEX = NACF each year','branch-to-property cash flows and value','12 affected residential floors','immutable source Model','year-end discounting and 2010 sale'],
},indent=2))
