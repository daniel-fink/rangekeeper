"""Run in Rhino 8. Set RK_COMPONENTS and RK_ACCEPTANCE_OUTPUT explicitly."""

import json
import os
import traceback

import clr
import Rhino
import System

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
clr.AddReference("Grasshopper")
import Grasshopper
from Grasshopper.Kernel import GH_Document, GH_DocumentIO
from Grasshopper.Kernel.Special import GH_Panel
from System.Drawing import PointF
from System.Reflection import BindingFlags

path = os.environ["RK_COMPONENTS"]
OUTPUT = os.environ["RK_ACCEPTANCE_OUTPUT"]
if not os.path.isdir(OUTPUT):
    os.makedirs(OUTPUT)
try:
    server = Grasshopper.Instances.ComponentServer
    if (
        server.EmitObjectProxy(System.Guid("b2e45ba7-af08-4b49-9612-0d9308ced601"))
        is None
    ):
        loaded = (
            server.GetType()
            .GetMethod("LoadGHA", BindingFlags.Instance | BindingFlags.NonPublic)
            .Invoke(
                server,
                System.Array[System.Object](
                    [Grasshopper.Kernel.GH_ExternalFile(path), False]
                ),
            )
        )
    # Exercise generic authoring revisions separately from the geometry example.
    generic = GH_Document()
    generic.Enabled = True

    def generic_add(obj, x, y):
        obj.CreateAttributes()
        obj.Attributes.Pivot = PointF(x, y)
        generic.AddObject(obj, False)
        return obj

    definitions_json = generic_add(GH_Panel(), 10, 10)
    definitions_json.UserText = "{}"
    entity_json = generic_add(GH_Panel(), 10, 100)
    entity_json.UserText = '{"name":"First"}'
    definitions = generic_add(
        server.EmitObject(System.Guid("b2e45ba7-af08-4b49-9612-0d9308ced601")), 250, 10
    )
    entity = generic_add(
        server.EmitObject(System.Guid("b2e45ba7-af08-4b49-9612-0d9308ced602")), 250, 100
    )
    model = generic_add(
        server.EmitObject(System.Guid("b2e45ba7-af08-4b49-9612-0d9308ced606")), 450, 10
    )
    encoded = generic_add(
        server.EmitObject(System.Guid("b2e45ba7-af08-4b49-9612-0d9308ced607")), 650, 10
    )
    definitions.Params.Input[0].AddSource(definitions_json)
    entity.Params.Input[0].AddSource(entity_json)
    model.Params.Input[0].AddSource(definitions.Params.Output[0])
    model.Params.Input[1].AddSource(entity.Params.Output[0])
    encoded.Params.Input[0].AddSource(model.Params.Output[0])
    generic.NewSolution(True)

    def output_model(component):
        return [str(x) for x in component.Params.Output[0].VolatileData.AllData(True)][
            0
        ]

    before = output_model(encoded)
    generic.NewSolution(True)
    if before != output_model(encoded):
        raise Exception("Unchanged recompute altered generic Model")
    entity_json.UserText = '{"name":"Second"}'
    entity_json.ExpireSolution(False)
    generic.NewSolution(True)
    changed = output_model(encoded)
    a = json.loads(before)
    b = json.loads(changed)
    if a["system"]["entities"][0]["id"] != b["system"]["entities"][0]["id"]:
        raise Exception("Editing name changed domain identity")
    if (
        a["metadata"]["id"] == b["metadata"]["id"]
        or b["metadata"].get("previous") != a["metadata"]["id"]
    ):
        raise Exception("Changed content did not advance revision")
    generic.NewSolution(True)
    if changed != output_model(encoded):
        raise Exception("Unchanged recompute lost revision lineage")
    gio = GH_DocumentIO()
    gio.Document = generic
    gio.SaveQuiet(os.path.join(OUTPUT, "generic-authoring.ghx"))
    reopened_generic = GH_DocumentIO()
    reopened_generic.Open(os.path.join(OUTPUT, "generic-authoring.ghx"))
    reopened_generic.Document.Enabled = True
    reopened_generic.Document.NewSolution(True)
    reopened_export = [
        x
        for x in reopened_generic.Document.Objects
        if x.ComponentGuid == encoded.ComponentGuid
    ][0]
    if changed != output_model(reopened_export):
        raise Exception("Reopening lost generic revision lineage")
    report = {
        "status": "passed",
        "rhino": str(Rhino.RhinoApp.Version),
        "runtime": str(System.Environment.Version),
        "generic_revisions": "stable identity; changed revision; retained previous after reopen",
    }
except Exception as error:
    report = {
        "error": traceback.format_exc(),
        "dotnet": str(error.clsException.ToString())
        if hasattr(error, "clsException")
        else repr(error),
    }
System.IO.File.WriteAllText(
    os.path.join(OUTPUT, "generic-report.json"), json.dumps(report, indent=2)
)
