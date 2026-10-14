"""Report the interpreter, dependencies and RK import used by this verification."""
import importlib.metadata as metadata
import json, platform, sys
import rangekeeper
names = ('linkml','linkml-runtime','jsonschema','PyYAML','numpy','scipy','pint',
         'polars','pandas','pyomo','highspy','pyxirr','nbformat','nbclient','mypy')
versions = {}
for name in names:
    try: versions[name] = metadata.version(name)
    except metadata.PackageNotFoundError: versions[name] = None
print(json.dumps({'python':sys.executable, 'version':platform.python_version(),
                  'rk':rangekeeper.__file__, 'packages':versions}, indent=2))
