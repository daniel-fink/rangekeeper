using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Threading.Tasks;

using Grasshopper.Kernel;
using Grasshopper.Kernel.Types;

using Speckle.Core.Models;
using Rangekeeper;

namespace Rangekeeper.Components
{
    public class AddProperties : GH_Component
    {
        public AddProperties()
            : base(
                "Add Properties to a Rangekeeper Entity",
                "ARkP",
                "Add Properties to a Rangekeeper Entity",
                "Rangekeeper",
                "Properties"
            )
        { }

        // protected override Bitmap Icon => Resources.AddPropertiesIcon;
        
        public override Guid ComponentGuid => new("E570E4F1-953A-4EF6-A1BA-1B1FA4CAFBA3");
        
        protected override void RegisterInputParams(GH_InputParamManager pManager)
        {
            pManager.AddGenericParameter(
                "Entity",
                "E",
                "Rangekeeper Entity",
                GH_ParamAccess.item);

            pManager.AddGenericParameter(
                "Attributes",
                "A",
                "Speckle Object of Key-Value attributes to add to this Entity.",
                GH_ParamAccess.item);
            pManager[1].Optional = true;
            
            pManager.AddGenericParameter(
                "Measurements",
                "M",
                "Speckle Object of Key-Number measurements to add to this Entity.",
                GH_ParamAccess.item);
            pManager[2].Optional = true;
        }
        
        protected override void RegisterOutputParams(GH_OutputParamManager pManager)
        {
            pManager.AddParameter(new EntityParam("Entity", "E", "Rangekeeper Entity", GH_ParamAccess.item));
        }

        protected sealed override void SolveInstance(IGH_DataAccess DA)
        {
            IGH_Goo? speckleGoo = null;
            DA.GetData(0, ref speckleGoo);
            
            if (!speckleGoo.CanConvertToEntity(out IEntity? ientity, out string? entityConvertRemark))
            {
                this.AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Error,
                    string.Format(
                        "Error: {0}.",
                        entityConvertRemark));
                return;
            }

            IGH_Goo? speckleAttribsGoo = null;
            DA.GetData(1, ref speckleAttribsGoo);

            Base attribsBase = null;
            if (speckleAttribsGoo is not null)
            {
                if (!speckleAttribsGoo.CanConvertToBase(out attribsBase, out string? attribConvertRemark))
                {
                    this.AddRuntimeMessage(GH_RuntimeMessageLevel.Error,
                        string.Format(
                            "Error: Input Attributes is not a Speckle Object: {0}.",
                            attribConvertRemark));
                    return;
                }
            }

            IGH_Goo? speckleMeasurementsGoo = null;
            DA.GetData(2, ref speckleMeasurementsGoo);
            Base measurementsBase = null;
            if (speckleMeasurementsGoo is not null)
            {
                if (!speckleMeasurementsGoo.CanConvertToBase(out measurementsBase, out string? measurementsConvertRemark))
                {
                    this.AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Error,
                        string.Format(
                            "Error: Input Measurements is not a Speckle Object: {0}.",
                            measurementsConvertRemark));
                    return;
                }
            }

            var entity = ientity.Copy(true);//.Duplicate();
            if (attribsBase is not null)
            {
                foreach (var attrib in attribsBase.GetMembers(DynamicBaseMemberType.Dynamic))
                {
                    if (attrib.Value is IGH_Goo goo)
                    {
                        var gooValue = goo.GetType().GetProperty("Value")?.GetValue(goo);
                        entity.AddAttribute(attrib.Key, gooValue.CloneViaSerialization());
                    }
                    else entity.AddAttribute(attrib.Key, attrib.Value.CloneViaSerialization());
                }
            }

            if (measurementsBase is not null)
            {
                foreach (var measurement in measurementsBase.GetMembers(DynamicBaseMemberType.Dynamic))
                {
                    double? number = null;
                    string? remark = null;

                    if (measurement.Value is IGH_Goo goo)
                    {
                        var gooValue = goo.GetType().GetProperty("Value")?.GetValue(goo);
                        if (gooValue.TryConvertToDouble(out number, out remark))
                            entity.AddMeasurement(measurement.Key, number);
                    }
                    else if (measurement.Value.TryConvertToDouble(out number, out remark))
                        entity.AddMeasurement(measurement.Key, number);
                    else
                    {
                        entity.AddMeasurement(measurement.Key, number);
                        this.AddRuntimeMessage(
                            GH_RuntimeMessageLevel.Warning,
                            string.Format(
                                "Warning: No value has been recorded for {0} as it is not a number: {1}",
                                measurement.Key,
                                remark));
                    }
                }
            }

            DA.SetData(0, entity);
        }
    }
}