"""Deliberate public IO/Run API misuse; exactly five errors are expected."""

import rangekeeper as rk
from rangekeeper.io import json, MemoryStore
from rangekeeper.run import validate

model: rk.Model = json.loads("{}", kind=rk.Run)
json.loads("{}", kind=dict)
MemoryStore().put({})
MemoryStore().load_run("not a UUID")
validate(rk.Model.from_data({}), resolver=MemoryStore())
