# -*- coding: utf-8 -*-
from setuptools import setup

packages = \
['rangekeeper', 'rangekeeper.dynamics', 'rangekeeper.models']

package_data = \
{'': ['*'], 'rangekeeper': ['book/*']}

install_requires = \
['Pint>=0.19.2,<0.20.0',
 'aenum>=3.1.11,<4.0.0',
 'matplotlib>=3.5.2,<4.0.0',
 'networkx>=2.8.2,<3.0.0',
 'numba>=0.55.2,<0.56.0',
 'pandas>=1.4.2,<2.0.0',
 'py-linq>=1.3.0,<2.0.0',
 'py-moneyed>=2.0,<3.0',
 'python-dateutil>=2.8.2,<3.0.0',
 'pyxirr>=0.7.2,<0.8.0',
 'scipy>=1.8.1,<2.0.0',
 'tabulate>=0.8.9,<0.9.0']

setup_kwargs = {
    'name': 'rangekeeper',
    'version': '0.1.0',
    'description': 'A Python library assisting financial modelling in scenario planning, decision-making, cashflow forecasting, and the like',
    'long_description': None,
    'author': 'Daniel Fink',
    'author_email': 'danfink@mit.edu',
    'maintainer': None,
    'maintainer_email': None,
    'url': None,
    'packages': packages,
    'package_data': package_data,
    'install_requires': install_requires,
    'python_requires': '>=3.9,<3.11',
}


setup(**setup_kwargs)
