Search.setIndex({"docnames": ["README", "basic_dcf", "deterministic_scenarios", "flexibility_intro", "intro", "market_dynamics"], "filenames": ["README.md", "basic_dcf.ipynb", "deterministic_scenarios.ipynb", "flexibility_intro.ipynb", "intro.md", "market_dynamics.ipynb"], "titles": ["Updating Documentation:", "A Basic Discounted Cash Flow Valuation", "Deterministic Scenario Analysis", "Introduction to Modeling Flexibility", "Exposition", "Real Estate Pricing Factor Dynamics"], "terms": {"make": [0, 2, 5], "sure": 0, "github": 0, "page": 0, "being": 0, "built": 0, "gh": 0, "branch": 0, "from": [0, 1, 2, 3, 5], "root": 0, "directori": 0, "ghp": 0, "import": [0, 1, 2, 3, 5], "instal": 0, "pip": 0, "build": [0, 1, 3, 5], "via": [0, 1, 5], "poetri": 0, "run": [0, 3, 5], "jupyt": [0, 2], "book": 0, "walkthrough": 0, "commit": 0, "ani": [0, 1, 3, 5], "chang": [0, 2, 3, 5], "main": 0, "while": [0, 5], "n": 0, "p": [0, 2], "f": 0, "_build": 0, "html": 0, "rangekeep": [0, 1, 2, 3, 5], "chapter": [1, 2, 3, 5], "1": [1, 2, 3, 5], "dng18": [1, 2, 3, 5], "showcas": 1, "structur": [1, 3], "function": [1, 3, 5], "dcf": [1, 2, 3, 5], "us": [1, 2, 3, 5], "real": [1, 3, 4], "estat": [1, 3, 4], "In": [1, 2, 3, 5], "thi": [1, 2, 3, 4, 5], "notebook": [1, 4], "core": 1, "comput": [1, 4, 5], "object": [1, 3, 5], "class": [1, 2, 3], "how": [1, 2, 3, 5], "thei": [1, 3, 5], "ar": [1, 2, 3, 5], "compos": 1, "togeth": [1, 3], "model": [1, 4, 5], "outlin": [1, 5], "To": [1, 3, 5], "do": [1, 5], "so": [1, 5], "we": [1, 2, 3, 5], "replic": [1, 2, 5], "tabl": [1, 2, 3, 5], "which": [1, 2, 3, 5], "describ": [1, 3, 5], "first": [1, 2, 3, 5], "need": [1, 3, 5], "neccesari": 1, "librari": [1, 2, 3, 5], "well": [1, 3, 5], "alia": 1, "rk": [1, 2, 3, 5], "panda": [1, 2, 3, 5], "pd": [1, 2, 3, 5], "analysi": [1, 4, 5], "sequenc": [1, 2, 3, 5], "movement": [1, 2, 3, 5], "currenc": [1, 2, 3], "whether": 1, "posit": [1, 5], "inflow": 1, "neg": [1, 5], "outflow": 1, "where": [1, 2, 3, 5], "each": [1, 2, 5], "associ": 1, "date": [1, 2, 3, 5], "quantiti": 1, "also": [1, 2, 5], "sometim": 1, "refer": [1, 5], "line": [1, 2, 3, 5], "item": [1, 3], "wai": [1, 3, 5], "design": 1, "subject": 1, "e": [1, 3, 5], "g": [1, 3, 5], "oper": [1, 2, 3, 5], "expens": [1, 2, 3, 5], "incom": [1, 2, 3, 5], "2": [1, 2, 3, 5], "s": [1, 2, 3, 5], "park": 1, "implement": [1, 5], "flux": [1, 2, 3, 5], "modul": [1, 5], "seri": [1, 2, 3, 4, 5], "encapsul": [1, 3], "materi": 1, "specifi": [1, 3, 5], "unit": [1, 2, 3], "like": [1, 2, 5], "energi": 1, "mass": 1, "etc": 1, "occur": [1, 2, 5], "note": [1, 3, 5], "index": [1, 2, 3], "datetimeindex": 1, "its": [1, 3, 5], "valu": [1, 3, 5], "float": 1, "initi": [1, 2, 5], "our": [1, 2, 3], "type": [1, 2, 3, 5], "measur": [1, 2, 3], "pint": 1, "definit": [1, 3, 5], "register_curr": [1, 2, 3], "aud": 1, "registri": [1, 2, 3], "print": [1, 3, 5], "australian": 1, "dollar": 1, "australia": 1, "coco": 1, "keel": 1, "island": 1, "christma": 1, "heard": 1, "mcdonald": 1, "kiribati": 1, "norfolk": 1, "nauru": 1, "tuvalu": 1, "next": [1, 5], "defin": [1, 3], "list": [1, 3], "amount": [1, 5], "transact": 1, "timestamp": [1, 2, 3, 5], "2020": [1, 5], "01": [1, 2, 3, 5], "100": [1, 2, 3, 5], "02": [1, 2, 3, 5], "200": [1, 5], "2019": [1, 5], "300": 1, "12": [1, 2, 3, 5], "31": [1, 2, 3, 5], "data": [1, 5], "cash_flow": 1, "name": [1, 2, 3, 5], "can": [1, 2, 3, 5], "view": 1, "just": [1, 5], "creat": [1, 2, 3], "simpli": [1, 2, 3], "call": 1, "00": [1, 2, 3, 5], "inspect": 1, "displai": 1, "0": [1, 2, 3, 5], "dtype": [1, 2], "float64": [1, 2], "datetime64": 1, "ns": 1, "freq": 1, "none": [1, 2, 3], "It": [1, 5], "properti": [1, 2, 3, 5], "As": [1, 2, 5], "you": [1, 5], "see": [1, 3, 5], "ha": [1, 2, 3, 5], "three": [1, 2], "stamp": 1, "follow": [1, 2, 5], "tempor": 1, "order": [1, 2, 3, 5], "convert": 1, "all": [1, 2, 3], "inform": [1, 3, 5], "method": [1, 2, 3, 5], "interv": 1, "time": [1, 2, 3, 5], "encompass": 1, "bound": [1, 2, 3, 5], "start": [1, 3, 5], "end": [1, 2, 3, 5], "start_dat": [1, 2, 3], "2001": [1, 2, 3, 5], "num_period": [1, 2, 3, 5], "11": [1, 2, 3, 5], "from_num_period": [1, 2, 3, 5], "period_typ": [1, 2, 3, 5], "period": [1, 2, 3, 5], "year": [1, 2, 3, 5], "2011": [1, 3, 5], "take": [1, 3, 5], "cast": 1, "over": [1, 5], "accord": 1, "logic": [1, 3], "There": 1, "two": [1, 3, 5], "form": [1, 2, 3, 5], "extrapol": [1, 2, 3], "gener": [1, 3, 5], "distribut": [1, 2, 3, 5], "total": [1, 5], "subdivid": 1, "match": [1, 5], "4": [1, 2, 3, 5], "potenti": [1, 2, 3, 5], "gross": [1, 2, 3, 5], "abov": [1, 5], "compound": [1, 2, 3, 5], "compounding_r": 1, "rate": [1, 2, 3, 5], "to_index": [1, 2, 3, 5], "let": [1, 2, 3, 5], "now": [1, 2, 3, 5], "previou": [1, 3, 5], "construct": [1, 3, 5], "initial_incom": [1, 2, 3], "potential_gross_incom": 1, "from_project": [1, 2, 3], "proj": [1, 2, 3], "2002": [1, 2, 3, 5], "102": [1, 3], "2003": [1, 2, 3, 5], "104": [1, 3], "04": [1, 2, 3, 5], "2004": [1, 2, 3, 5], "106": [1, 3], "121": [1, 3], "2005": [1, 2, 3, 5], "108": [1, 3], "243": [], "2006": [1, 2, 3, 5], "110": [1, 3], "408": [], "2007": [1, 2, 3, 5], "112": [1, 3], "616": [], "2008": [1, 2, 3, 5], "114": [1, 3], "869": [], "2009": [1, 2, 3, 5], "117": [1, 3], "166": [], "2010": [1, 2, 3, 5], "119": [1, 3], "509": [], "899": [], "similarli": [1, 2, 3], "vacanc": [1, 2, 3], "multipli": [1, 3, 5], "vacancy_r": [1, 2, 3], "05": [1, 2, 3, 5], "allow": [1, 2, 3], "5": [1, 3, 5], "202": [], "30604": [], "41216": [], "5204": [], "63081": [], "74343": [], "8583": [], "97546": [], "6": [1, 3, 5], "09497": [], "sign": 1, "becaus": [1, 5], "an": [1, 2, 3, 5], "collect": 1, "constitu": 1, "resampl": 1, "effect": [1, 2, 3, 5], "illustr": 1, "concept": [1, 2], "effective_gross_income_stream": [], "10": [1, 2, 3, 5], "20": [1, 3, 5], "24": [1, 3], "41": [1, 2, 3, 5], "52": [1, 3, 5], "62": [1, 3], "63": [1, 3, 5], "87": [1, 2, 3, 5], "74": [1, 2, 3, 5], "17": [1, 3, 5], "86": [1, 3, 5], "51": [1, 3, 5], "98": [1, 3, 5], "90": [1, 3], "09": [1, 3, 5], "own": [1, 5], "aggreg": [1, 5], "sum": [1, 2, 3], "them": [1, 3, 5], "result": [1, 3, 5], "effective_gross_income_flow": 1, "95": [1, 3, 5], "96": [1, 2, 3, 5], "9": [1, 3], "838": [], "815": [], "831": [], "888": [], "985": [], "109": [1, 3], "125": [], "111": [1, 3], "308": [], "113": [1, 3], "534": [], "115": [1, 3], "804": [], "back": [1, 5], "With": 1, "mind": 1, "complet": 1, "opex_pgi_ratio": [1, 2, 3], "35": [1, 2, 3, 5], "operating_expens": 1, "invert": [1, 2, 3], "net_operating_incom": 1, "net": [1, 2, 3, 5], "70": [1, 3, 5], "84": [1, 3], "36": [1, 3, 5], "81": [1, 3, 5], "37": [1, 3, 5], "14": [1, 3, 5], "83": [1, 2, 3, 5], "89": [1, 3, 5], "38": [1, 3, 5], "64": [1, 3], "99": [1, 3], "39": [1, 3, 5], "42": [1, 2, 3, 5], "13": [1, 2, 3, 5], "40": [1, 3, 5], "53": [1, 3, 5], "80": [1, 3, 5], "66": [1, 3], "capex_pgi_ratio": [1, 2, 3], "capital_expenditur": 1, "capit": [1, 2, 3, 5], "expenditur": [1, 2, 3, 5], "net_annual_cashflow": 1, "annual": [1, 2, 3, 5], "cashflow": [1, 2, 3], "60": [1, 3], "61": [1, 3, 5], "67": [1, 3], "82": [1, 3], "57": [1, 2, 3, 5], "26": [1, 2, 3, 5], "68": [1, 3, 5], "92": [1, 2, 3, 5], "49": [1, 3, 5], "30": [1, 3, 5], "72": [1, 2, 3, 5], "71": [1, 3, 5], "73": [1, 3], "19": [1, 3, 5], "calcul": [1, 2, 3, 5], "revers": [1, 2, 3, 5], "set": [1, 2, 3, 5], "up": [1, 2, 3, 5], "10th": 1, "reversion_span": [1, 3], "dateoffset": 1, "exit_capr": [1, 2, 3], "reversion_flow": 1, "uniform": [1, 2, 3, 5], "1218": [], "final": 1, "net_cashflows_with_revers": 1, "trim_to_span": [1, 2, 3], "end_dat": [1, 2, 3], "50": [1, 2, 3, 5], "06": [1, 3, 5], "54": [1, 3, 5], "55": [1, 3], "56": [1, 3, 5], "43": [1, 2, 3, 5], "58": [1, 2, 3, 5], "59": [1, 2, 3, 5], "75": [1, 3], "given": [1, 2, 5], "7": [1, 3, 5], "present": [1, 2, 3], "pv": [1, 2, 3, 5], "discount_r": [1, 2, 3], "07": [1, 2, 3, 5], "46": [1, 3, 5], "729": [], "44": [1, 3, 5], "5454": [], "4638": [], "4795": [], "588": [], "7848": [], "0659": [], "33": [1, 3], "4273": [], "8653": [], "650": 1, "051": [], "project_pv": 1, "collaps": [1, 2, 3], "round": [1, 2, 3], "1000": [1, 2, 3, 5], "r": 1, "de": 1, "neufvil": 1, "d": 1, "geltner": 1, "flexibl": [1, 2, 4, 5], "under": [1, 4], "uncertainti": [1, 4, 5], "practic": 1, "guid": 1, "develop": [1, 3], "john": 1, "wilei": 1, "son": 1, "ltd": 1, "2018": [1, 5], "isbn": 1, "9781119106470": 1, "url": 1, "http": [1, 5], "onlinelibrari": 1, "com": 1, "doi": 1, "ab": 1, "1002": 1, "arxiv": 1, "pdf": 1, "org": [1, 5], "variou": [2, 5], "vari": [2, 5], "kei": [2, 5], "input": [2, 3, 5], "modyf": 2, "certain": [2, 3, 5], "produc": [2, 3], "integr": [2, 5], "step": 2, "singl": [2, 3, 5], "accept": 2, "dictionari": 2, "easili": [2, 5], "altern": [2, 3], "specif": [2, 3, 5], "recreat": 2, "again": [2, 5], "necessari": 2, "These": [2, 5], "format": [2, 3, 5], "usd": [], "param": [2, 3], "acquisition_cost": [2, 3], "growth_rat": [2, 3, 5], "absorb": 2, "addit": [2, 3, 5], "straight": [2, 3], "addl_pgi_init": 2, "addl_pgi_slop": 2, "Then": 2, "dict": [2, 3], "def": [2, 3], "__init__": [2, 3], "self": [2, 3], "more": [2, 3, 4, 5], "readabl": 2, "update_class": [2, 3], "decor": 2, "sequenti": 2, "add": 2, "cell": [2, 5], "help": 2, "when": [2, 3], "document": 2, "init_span": [2, 3], "calc_span": [2, 3], "acq_span": [2, 3], "acquisit": [2, 3], "offset_d": [2, 3], "shift": [2, 3, 5], "init_flow": 2, "project": [2, 3, 5], "base_pgi": 2, "addl_pgi": 2, "straightlin": 2, "slope": 2, "pgi": [2, 3], "stream": [2, 3, 5], "egi": [2, 3], "opex": [2, 3], "noi": [2, 3, 5], "capex": [2, 3], "net_cf": [2, 3], "dropna": [2, 3], "intern": [2, 3], "return": [2, 3, 5], "irr": [2, 3], "calc_metr": [2, 3], "cumulative_net_cf": [2, 3], "cumul": [2, 3, 5], "loc": [2, 3], "cumulative_net_cfs_with_rev": 2, "append": [2, 3], "incl_acq": [2, 3], "xirr": [2, 3], "concat": [2, 3], "panel": 2, "b": 2, "increas": 2, "ad": [2, 5], "3": [2, 3, 5], "optimistic_param": 2, "copi": [2, 3], "new": [2, 3], "1128": [], "1153": [], "1177": [], "23": [2, 3], "1198": [], "1236": [], "1252": [], "85": [2, 3], "1267": [], "1281": [], "1294": [], "08": [2, 3, 5], "207": [], "1512": [], "1327": [], "1232": [], "1173": [], "1132": [], "1101": [], "1077": [], "1058": [], "1042": [], "c": 2, "pessimistic_param": 2, "871": 2, "963": [], "846": 2, "284": [], "822": 2, "774": [], "801": 2, "781": 2, "582": [], "763": 2, "591": [], "747": 2, "15": [2, 3, 5], "732": 2, "134": [], "718": 2, "427": [], "705": 2, "922": [], "067": [], "0177": [], "0006": [], "0081": [], "0134": [], "017": [], "0196": [], "0216": [], "0232": [], "0245": [], "continu": [2, 5], "outcom": [2, 3, 5], "both": [2, 5], "have": [2, 3, 5], "chanc": 2, "And": [2, 5], "er": 2, "07000": 2, "06675": 2, "06605": 2, "06565": 2, "06535": 2, "06510": 2, "06485": 2, "06465": 2, "06450": 2, "06435": 2, "assum": [2, 5], "possibl": [2, 5], "sell": [2, 3, 5], "value_of_flex": 2, "02036601269492": 2, "simul": [3, 5], "multipl": [3, 5], "proforma": [3, 5], "numpi": [], "np": [], "tqdm": [], "seaborn": [], "sn": [], "matplotlib": [], "pyplot": [], "plt": [], "overal": 3, "durat": 5, "span": 3, "mokdel": [], "situat": [3, 5], "cap_rat": [3, 5], "growth_rate_dist": [], "symmetr": [3, 5], "triangular": [3, 5], "mean": [3, 5], "0005": 5, "residu": [3, 5], "005": [], "initial_value_dist": [], "from_likelihood": [], "growth": [3, 5], "initial_valu": [3, 5], "2408": [], "7497": [], "volatility_per_period": [3, 5], "autoregression_param": [3, 5], "mean_reversion_param": [3, 5], "space_cycle_period_mean": [], "space_cycle_period_residu": [], "space_cycle_height_mean": [], "space_cycle_height_residu": [], "space_cycle_phase_prop_mean": [], "space_cycle_phase_prop_residu": [], "asset_cycle_period_diff_mean": [], "asset_cycle_period_diff_residu": [], "asset_cycle_amplitude_mean": [], "asset_cycle_amplitude_residu": [], "space_cycle_asymmetric_parameter_mean": [], "space_cycle_asymmetric_parameter_residu": [], "asset_cycle_asymmetric_parameter_mean": [], "asset_cycle_asymmetric_parameter_residu": [], "space_cycle_period_dist": [], "space_cycle_height_dist": [], "space_cycle_phase_prop_dist": [], "asset_cycle_phase_prop_dist": [], "asset_cycle_period_diff_dist": [], "asset_cycle_amplitude_dist": [], "space_cycle_asymmetric_parameter_dist": [], "asset_cycle_asymmetric_parameter_dist": [], "lineplot": [], "space_waveform": [3, 5], "ax": [], "ylabel": [], "space": [3, 5], "cycl": [3, 5], "waveform": 5, "nois": 3, "noise_dist": [3, 5], "black_swan": [3, 5], "blackswan": [3, 5], "likelihood": [3, 5], "dissipation_r": [3, 5], "probabl": [3, 5], "impact": [3, 5], "25": [3, 5], "futur": 5, "histori": [], "critic": [], "provid": 5, "flow": [3, 4, 5], "The": [3, 5], "price": [2, 3, 4], "factor": [3, 4], "adjust": 3, "rent": 5, "impli": [3, 5], "cap": [3, 5], "disposit": 5, "asset": [3, 5], "sale": 3, "last": 5, "market_dynam": [], "initial_r": [], "market_proj": [], "volatility_param": [], "cyclicality_param": [], "market_param": [], "nameerror": [], "traceback": [], "most": 5, "recent": [], "pricing_factor": [], "market_trend": [], "space_market_price_factor": [3, 5], "implied_rev_cap_r": [3, 5], "decim": [], "plot": [3, 5], "exampl": 5, "same": [3, 5], "one": [], "previous": [], "except": [3, 5], "determinist": [3, 4, 5], "rather": [], "stochast": 5, "depend": [], "model_param": [], "expostinflexiblemodel": [], "product": 3, "pbtcf": 3, "expostinflex_model": [], "mani": [], "get": 3, "sens": 5, "output": [3, 5], "infer": [], "about": 5, "iterations_count": [], "int": [], "mode": [], "trend_param": [], "trend_mean": 5, "trend_residu": 5, "rent_mean": [], "rent_residu": [], "model_sampl": [], "prun": [], "q": [], "l": [], "t": 5, "prun0": [], "open": [], "read": [], "pool": [], "8": [3, 5], "iter": 5, "map_async": [], "_": [], "rang": [3, 5], "readi": [], "fals": 3, "sleep": [], "yield": 5, "pass": 3, "to_fram": [], "histplot": [], "kde": [], "true": [3, 5], "ecdfplot": [], "agg": [], "median": [], "std": [], "skew": 5, "kurtosi": [], "cite": [], "farevuu2018": [], "expand": 4, "horizon": [], "consid": 5, "basic": [3, 4], "linear": [], "explor": [], "fulli": [], "case": [3, 5], "For": [3, 5], "tradit": [3, 5], "extend": [], "number": 5, "much": 5, "larger": [], "repres": 5, "befor": 3, "stop": 3, "gain": 3, "rule": 3, "trigger": 3, "A": [4, 5], "soon": [], "rise": [], "pre": [], "level": 5, "matter": [], "what": 5, "methodolog": 5, "behind": [], "condit": 3, "statement": [], "control": [], "program": 3, "command": [], "decis": 3, "encount": [], "autom": [], "process": [3, 5], "mimick": [], "investor": 3, "manag": 3, "would": [3, 5], "valuat": [2, 4], "robust": 4, "framework": 4, "discount": [4, 5], "cash": [3, 4, 5], "scenario": [3, 4], "dynam": [3, 4], "market": [], "introduct": 4, "repeat": [], "sampl": 5, "base": 5, "circumst": 5, "qualiti": 5, "characterist": [3, 5], "identifi": 5, "non": [3, 5], "substitut": 5, "fungibl": 5, "ineffici": 5, "autoregress": 5, "should": 5, "includ": 5, "random": 5, "walk": 5, "ratio": 5, "origin": 5, "pro": [3, 5], "forma": [3, 5], "expect": 5, "arriv": 5, "captur": [3, 5], "histor": [3, 5], "variat": 5, "observ": 5, "interpret": 5, "avail": 5, "substanti": 5, "enhanc": 5, "recogn": 5, "special": 5, "featur": 5, "offer": 5, "richer": 5, "fuller": 5, "pictur": 5, "than": 5, "figur": [3, 5], "doe": 5, "explicitli": 5, "formul": [3, 5], "incorpor": 5, "later": 5, "exercis": [3, 5], "accompani": [3, 5], "excel": [3, 5], "spreadsheet": [3, 5], "detail": 5, "mktdynamicsinput": 5, "tab": 5, "five": 5, "intwo": [], "mostli": 5, "variabl": 5, "those": 5, "explicit": 5, "introduc": [3, 5], "specifii": 5, "some": 5, "extra": 5, "2025": 5, "rental": 5, "exclud": 5, "requir": [3, 5], "paramet": [3, 5], "long": 5, "around": 5, "toward": 5, "revert": 5, "relat": 5, "go": [3, 5], "out": 5, "appli": [3, 5], "upon": 5, "resal": [3, 5], "inflex": 5, "10yr": 5, "exactli": 5, "yr11": 5, "divid": 5, "below": [3, 5], "tend": 5, "favor": [3, 5], "earlier": 5, "mitig": 5, "maxim": 5, "unfavor": 5, "between": 5, "bui": 5, "plausibl": 5, "equal": 5, "minu": [3, 5], "plu": 5, "basi": [3, 5], "point": 5, "improv": 5, "govern": 5, "fraction": 5, "normal": 5, "give": 5, "subsequ": 5, "estim": 5, "half": 5, "proport": 5, "enter": 5, "want": 5, "typic": 5, "wouldn": 5, "here": 5, "abl": 5, "pretti": 5, "accur": 5, "realist": [3, 5], "especi": 5, "exist": 5, "central": 5, "tendenc": 5, "entir": 5, "onli": [3, 5], "rel": [3, 5], "TO": 5, "contain": 5, "default": 5, "zero": 5, "principl": 5, "howev": 5, "increment": 5, "slightli": 5, "counteract": 5, "minor": 5, "inconsist": 5, "upward": 5, "bia": 5, "mai": [3, 5], "interact": 5, "other": 5, "element": 5, "ideal": 5, "better": [3, 5], "appl": 5, "comparison": 5, "inflxpv": 5, "proformapv": 5, "k13": 5, "almost": 5, "alwai": [3, 5], "absolut": 5, "lr": 5, "assumpt": 5, "awai": 5, "throughout": 5, "small": 5, "unless": 5, "great": 5, "averag": [3, 5], "economi": 5, "perhap": 5, "emerg": 5, "countri": 5, "nomin": 5, "inflat": 5, "anywai": 5, "0500": 5, "0000": 5, "onc": 5, "structr": [], "0475": 5, "0525": 5, "standard": 5, "deviat": 5, "across": 5, "longitudin": 5, "dispers": 5, "differ": [3, 5], "accumul": 5, "realiz": 5, "becom": 5, "embed": 5, "forward": 5, "whose": [3, 5], "top": 5, "track": [], "column": [], "innov": [], "If": [1, 5], "affect": 5, "evid": 5, "indic": [3, 5], "matur": 5, "u": 5, "individu": 5, "idiosyncrat": 5, "risk": 5, "term": [3, 5], "stabil": 5, "reflect": 5, "gaussian": [], "But": [], "empir": 5, "inertia": 5, "overriden": [], "dashboard": [], "relev": [], "degre": 5, "automat": 5, "compon": 5, "current": 5, "liquid": 5, "information": 5, "effici": 5, "stock": 5, "might": 5, "leav": 5, "noisi": 5, "deal": 5, "separ": 5, "farther": [], "right": [], "bake": [], "greater": 5, "must": 3, "momentum": 5, "neighborhood": [], "determin": 5, "strength": 5, "speed": 5, "elimin": [], "veri": 5, "close": 5, "were": 5, "sheet": 5, "impart": 5, "pull": 5, "reduc": 5, "suggest": 5, "appropri": 5, "distinct": 5, "respect": [3, 5], "rent_market": 5, "somewhat": 5, "predict": 5, "fact": 5, "necessarili": 5, "sync": 5, "anoth": 5, "latter": 5, "sine": 5, "amplitud": 5, "phase": [3, 5], "asymmetr": 5, "curv": 5, "sharp": 5, "quick": 5, "notic": 5, "downturn": [3, 5], "oppos": 5, "upturn": 5, "seem": 5, "randomli": 5, "anywher": [], "peak": [3, 5], "trough": [3, 5], "rent_cycle_span_mean": [], "rent_cycle_period_avg": [], "think": 5, "know": 5, "relationship": [], "bottom": 5, "head": 5, "mid": [3, 5], "down": [], "pleas": [], "asymetr": [], "formula": [], "off": 5, "65": [], "closer": [], "uniformli": [], "upsw": [], "late": [], "boom": [], "175": [], "full": 5, "invest": [3, 5], "been": [3, 5], "occup": 5, "leverag": 5, "fix": [3, 5], "revenu": 5, "actual": 5, "usual": 5, "too": 5, "far": 5, "henc": [], "rememb": [], "either": 5, "quarter": 5, "rent_cycle_span": [], "cap_rate_cycle_period": [], "bit": [], "less": [], "fifth": [], "keep": [], "magnitud": [], "swing": [], "correspond": [], "roughli": [], "thing": [], "denomin": [], "ex": [], "post": [], "from_param": [], "space_cycle_period": [3, 5], "space_cycle_phas": [], "space_cycle_amplitud": [], "space_cycle_asymmetric_paramet": [3, 5], "asset_cycle_period": [], "asset_cycle_phas": [], "asset_cycle_amplitud": [3, 5], "asset_cycle_asymmetric_paramet": [3, 5], "visual": 5, "pure": 5, "market_wav": 5, "wave": 5, "asset_waveform": [3, 5], "015": [], "unforese": [], "event": 5, "look": [3, 5], "historical_valu": [3, 5], "composit": [], "space_market": [3, 5], "asset_true_valu": [3, 5], "noisy_valu": [3, 5], "surround": 5, "modifi": 5, "pert": 5, "densiti": 5, "reli": 5, "minimum": [3, 5], "maximum": 5, "weight": 5, "approxim": 5, "scale": 5, "drawn": 5, "impress": 5, "ones": 5, "label": [], "0502": [], "count": 3, "0148": [], "from_trend": [], "graph": 3, "attributeerror": [], "attribut": 5, "0608": [], "0010": [], "0576": [], "9982": [], "thu": [3, 5], "intial": 5, "perform": 5, "sensit": 5, "0553": [], "9986": [], "per": 5, "0593": [], "9991": [], "effective_gross_incom": 1, "wish": 1, "1278": [], "0427": [], "9983": [], "offset": 5, "height": 5, "_from_estim": [], "sinc": 5, "en": 5, "wikipedia": 5, "wiki": 5, "phase_": 5, "distanc": 5, "ie": [3, 5], "doubl": 5, "slippag": 5, "mayb": 5, "size": [3, 5], "unrel": 5, "resembl": 5, "sawtooth": 5, "often": 5, "sharper": 5, "quicker": 5, "recoveri": 5, "asymmetri": 5, "extrem": 5, "immedi": 5, "twice": 5, "0480": [], "from_estim": [3, 5], "space_cycle_phase_prop": [3, 5], "space_cycle_height": [3, 5], "asset_cycle_period_diff": [3, 5], "asset_cycle_phase_prop": [3, 5], "025": 5, "similar": [3, 5], "unlik": 5, "directli": 5, "By": 5, "re": [3, 5], "though": 5, "sampleabl": 5, "come": 5, "surpris": 5, "major": 5, "outsid": 5, "simplifi": 5, "natur": [3, 5], "dissip": 5, "yet": 5, "could": 5, "consist": [3, 5], "experi": 5, "geometr": 5, "alreadi": 5, "calibr": 5, "presum": 5, "against": [3, 5], "0517": [], "9906": [], "0479": [], "0083": [], "statist": 5, "good": 5, "autoregressive_return": [3, 5], "asset_market": [3, 5], "29": [3, 5], "32": [3, 5], "03": [3, 5], "18": [3, 5], "28": [2, 3, 5], "34": [3, 5], "79": 3, "69": 3, "45": [3, 5], "47": [3, 5], "2012": 5, "21": [2, 3], "2013": 5, "91": [3, 5], "88": [3, 5], "2014": 5, "2015": 5, "48": [1, 3], "2016": 5, "2017": 5, "78": [1, 3], "76": 5, "22": [3, 5], "2021": 5, "2022": 5, "16": [3, 5], "2023": 5, "2024": 5, "sourc": 5, "shown": 5, "valueerror": 3, "file": [], "cach": [], "pypoetri": [], "virtualenv": [], "l7": [], "mcx": [], "py3": [], "lib": [], "python3": [], "site": [], "packag": [], "ipython": [], "formatt": [], "py": [], "344": [], "baseformatt": [], "__call__": [], "obj": [], "342": [], "get_real_method": [], "print_method": [], "343": [], "345": [], "346": [], "els": 3, "_repr_html_": [], "_format_seri": [], "93": [], "94": 5, "to_markdown": [], "tablefmt": [], "check": 3, "27": 3, "str": [], "local": [1, 2, 3], "group": 3, "floatfmt": [], "listcomp": [], "pyenv": [], "version": [], "273": [], "val": [], "symbol": [], "271": [], "digit": [], "conv": [], "int_frac_digit": [], "frac_digit": [], "272": [], "127": [], "rais": [], "274": [], "276": [], "_local": [], "monetari": [], "277": [], "marker": [], "insert": [], "0x2a79d2dd0": [], "000": [2, 3], "0x2a7fd7ca0": [], "0x2c9335300": [], "optim": 2, "respons": 3, "begin": 3, "trial": 3, "deterministic_scenario": 3, "ipynb": 3, "setlocal": [1, 2, 3], "lc_all": [1, 2, 3], "realistic_trad": [], "020": [], "040": [], "061": [], "082": [], "126": [], "148": [], "171": [], "195": [], "218": [1, 2, 3], "realistic_trad_t": [], "ant": [], "metric": 3, "occ": 3, "0765": [], "1850": [], "keyerror": [], "387": [], "386": [], "_format_flow": [], "388": [], "stralign": [], "389": [], "numalign": [], "390": [], "391": [], "2f": [], "400": [], "398": [], "399": [], "to_period": [], "formatted_flow": [], "401": [], "402": [], "403": [], "404": [], "_format_mov": [], "_resampled_flow": [], "405": [], "frame": [], "axi": [], "fillna": [], "sort_index": [], "facet": [], "plain": [], "351": [], "plainquant": [], "dimens": [], "349": [], "unitlik": [], "bool": 3, "350": [], "dimension": [], "_registri": [], "get_dimension": [], "643": [], "plainregistri": [], "input_unit": [], "639": [], "todo": [], "to_units_contain": [], "640": [], "tri": [], "repars": [], "fail": [], "641": [], "_get_dimension": [], "660": [], "657": [], "659": [], "defaultdict": [], "_get_dimensionality_recurs": [], "662": [], "663": [], "del": [], "675": [], "ref": [], "exp": [], "673": [], "exp2": [], "674": [], "_is_dim": [], "reg": [], "_dimens": [], "676": [], "is_bas": [], "677": [], "0x2e041e380": [], "en_au": [1, 2, 3], "278": 1, "128": [2, 3], "153": 2, "177": 2, "198": 2, "236": 2, "252": 2, "267": 2, "281": 2, "294": 2, "77": [2, 5], "basemodel": 3, "calc_acquisit": 3, "calc_egi": 3, "calc_noi": 3, "calc_ncf": 3, "calc_revers": 3, "cumulative_net_cf_with_rev": 3, "ex_ant": 3, "ex_ante_t": 3, "hold": 3, "lock": [], "fundament": 3, "econom": 3, "2000": 3, "050747414": 3, "002537905": 3, "duplic": 3, "edit": 3, "subclass": 3, "expostinflexmodel": 3, "super": [], "ex_post_param": 3, "ex_post_inflex": 3, "ex_post_t": 3, "124": [], "118": [], "645": [], "compar": 3, "707": [], "1816": [], "2434": [], "invers": 5, "therefor": 5, "easier": 5, "envis": 5, "397": [], "396": [], "410": [], "409": [], "411": [], "412": [], "413": [], "414": [], "415": [], "0x2e3bfdb10": [], "deriv": 3, "107": [], "101": [], "145": [], "170": [], "161": [], "167": [], "159": [], "553": [], "0897": [], "7703": [], "156": [], "97": 5, "147": [], "140": [], "143": 3, "136": 3, "149": [], "141": [], "137": [], "453": [], "0799": [], "6304": [], "122": [], "116": [], "144": [], "151": [], "130": [], "138": [], "131": [], "142": [], "135": 3, "617": [], "8686": [], "overrid": 3, "instead": 3, "105": [], "132": [], "133": [], "393": [], "2878": [], "7924": [], "120": 3, "176": [], "157": [], "316": [], "566": [], "pv_diff": 3, "percentag": 3, "irr_diff": 3, "attempt": 3, "abil": 3, "option": 3, "creation": 3, "cours": 3, "action": 3, "oblig": 3, "simpl": 3, "problem": 3, "question": 3, "decid": 3, "polici": [], "execis": 3, "154": [], "146": [], "129": [], "445": [], "612": [], "442": [], "634": [], "123": [], "169": [], "160": [], "181": [], "172": [], "188": [], "179": [], "235": [], "223": [], "232": [], "221": [], "139": [], "540": [], "164": [], "152": [], "357": [], "648": [], "168": 3, "189": [], "561": [], "736": [], "493": [], "syntaxerror": [], "invalid": [], "syntax": [], "wrap": 3, "378": [], "568": [], "set_param": 3, "execut": 3, "trend": 3, "volatil": 3, "cyclic": 3, "black": 3, "swan": 3, "set_market": 3, "514": [], "627": [], "overwrit": 3, "enabl": 3, "state": 3, "met": 3, "diagram": 3, "flowchart": 3, "influenc": 3, "bring": 3, "boolean": 3, "flag": 3, "code": 3, "prevent": 3, "few": 3, "exceed_pricing_factor": 3, "threshold": 3, "i": 3, "manipul": 3, "adjust_hold_period": 3, "try": 3, "idx": 3, "len": 3, "policy_param": 3, "updat": 3, "instanc": 3, "context": 3, "abstract": 3, "chain": 3, "complex": 3, "mimic": 3, "markov": 3, "stop_gain_resale_polici": 3, "ex_post_flex": 3, "301": [], "benefit": 3, "encourag": 3, "longer": [], "through": [], "worth": [], "162": [], "158": [], "510": [], "683": [], "269": [], "emul": 3, "187": [], "178": [], "193": [], "183": [], "430": [], "702": [], "422": [], "173": [], "165": [], "439": [], "681": [], "224": [], "213": [], "237": [], "226": [], "222": [], "211": [], "150": [], "608": [], "896": [], "355": [], "492": [], "652": [], "313": [], "until": 3, "avoid": 3, "424": 3, "557": 3}, "objects": {}, "objtypes": {}, "objnames": {}, "titleterms": {"updat": 0, "document": 0, "A": 1, "basic": 1, "discount": 1, "cash": [1, 2], "flow": [1, 2], "valuat": 1, "The": 1, "foundat": 1, "element": 1, "proforma": [1, 2], "overview": 1, "span": [1, 2, 5], "project": 1, "stream": 1, "bibliographi": 1, "determinist": 2, "scenario": [2, 5], "analysi": 2, "base": [2, 3], "paramet": 2, "model": [2, 3], "metric": 2, "output": 2, "optimist": 2, "pessimist": 2, "expect": 2, "valu": 2, "ev": 2, "introduct": 3, "flexibl": 3, "market": [3, 5], "dynam": 5, "trend": 5, "volatil": 5, "cyclic": 5, "result": [], "repeat": [], "sampl": [], "resal": [], "time": [], "dcf": [], "exposit": 4, "real": 5, "estat": 5, "price": 5, "factor": 5, "from": [], "scratch": [], "overal": 5, "produc": 5, "multipl": [], "nois": 5, "black": 5, "swan": 5, "statist": [], "put": 5, "all": 5, "togeth": 5, "one": 5, "trial": 5, "ex": 3, "ant": 3, "inflex": 3, "post": 3, "polici": 3}, "envversion": {"sphinx.domains.c": 2, "sphinx.domains.changeset": 1, "sphinx.domains.citation": 1, "sphinx.domains.cpp": 6, "sphinx.domains.index": 1, "sphinx.domains.javascript": 2, "sphinx.domains.math": 2, "sphinx.domains.python": 3, "sphinx.domains.rst": 2, "sphinx.domains.std": 2, "sphinx.ext.intersphinx": 1, "sphinxcontrib.bibtex": 9, "sphinx": 56}})