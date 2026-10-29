"""Deliberate public IO/Run API misuse; exactly five errors are expected."""

import rangekeeper as rk
from rangekeeper.io import MemoryStore, json
from rangekeeper.run import validate

model: rk.Model = json.loads(text="{}", kind=rk.Run)
json.loads(text="{}", kind=dict)
MemoryStore().put({})
MemoryStore().load_run("not a UUID")
validate(run=rk.Model.from_data(data={}), resolver=MemoryStore())
