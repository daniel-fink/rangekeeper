// using System;
// using Grasshopper.Kernel;
// using Grasshopper.Kernel.Types;
// using Speckle.Core.Models;
//
// namespace Rangekeeper.Components
// {
//     public class AddProperties : GH_Component
//     {
//         public AddProperties()
//             : base(
//                 "Add Properties to a Rangekeeper Entity",
//                 "ARkP",
//                 "Add Properties to a Rangekeeper Entity",
//                 "Rangekeeper",
//                 "Properties"
//             )
//         { }
//
//         // protected override Bitmap Icon => Resources.AddPropertiesIcon;
//         
//         public override Guid ComponentGuid => new("E570E4F1-953A-4EF6-A1BA-1B1FA4CAFBA3");
//         
//         protected override void RegisterInputParams(GH_InputParamManager pManager)
//         {
//             pManager.AddGenericParameter(
//                 "Entity",
//                 "E",
//                 "Rangekeeper Entity",
//                 GH_ParamAccess.item);
//
//             pManager.AddGenericParameter(
//                 "Attributes",
//                 "A",
//                 "Speckle Object of Key-Value attributes to add to this Entity.",
//                 GH_ParamAccess.item);
//             pManager[1].Optional = true;
//             
//             pManager.AddGenericParameter(
//                 "Measurements",
//                 "M",
//                 "Speckle Object of Key-Number measurements to add to this Entity.",
//                 GH_ParamAccess.item);
//             pManager[2].Optional = true;
//         }
//         
//         protected override void RegisterOutputParams(GH_OutputParamManager pManager)
//         {
//             pManager.AddParameter(new EntityParam("Entity", "E", "Model Entity", GH_ParamAccess.item));
//         }
//
//         protected sealed override void SolveInstance(IGH_DataAccess DA)
//         {
//             GH_Entity? speckleGoo = null;
//             if (!DA.GetData("Entity", ref speckleGoo))
//             {
//                 this.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, string.Format("Error: Entity Input was not a Rangekeeper Entity."));
//                 return;
//             }
//             // this.AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, speckleGoo.SerializeToJson());
//             // this.AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, speckleGoo.GetType().SerializeToJson());
//             // this.AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, speckleGoo.Value.SerializeToJson());
//             // this.AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, speckleGoo.Value.GetType().SerializeToJson());
//             // this.AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, speckleGoo.Value.GetAttributes().GetType().SerializeToJson());
//
//
//             IGH_Goo? speckleAttribsGoo = null;
//             Base? speckleAttribsBase = null;
//             if (DA.GetData("Attributes", ref speckleAttribsGoo));
//             {
//                 if (speckleAttribsGoo is not null)
//                     if (!speckleAttribsGoo.CanConvertToBase(out speckleAttribsBase, out string? remark))
//                     {
//                         this.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, remark);
//                         return;
//                     }
//             }
//
//             IGH_Goo? speckleMeasurementsGoo = null;
//             Base? speckleMeasurementsBase = null;
//             if (DA.GetData("Measurements", ref speckleMeasurementsGoo));
//             {
//                 if (!speckleMeasurementsGoo.CanConvertToBase(out speckleMeasurementsBase, out string? remark))
//                 {
//                     this.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, remark);
//                     return;
//                 }
//             }
//             
//             var entity = speckleGoo.Value.Clone();
//
//             if (speckleAttribsBase is not null)
//             {
//                 foreach (var attrib in speckleAttribsBase.GetMembers(DynamicBaseMemberType.Dynamic))
//                 {
//                     if (attrib.Value is IGH_Goo goo)
//                     {
//                         var gooValue = goo.GetType().GetProperty("Value")?.GetValue(goo);
//                         entity.GetAttributes()[attrib.Key] = gooValue;
//                     }
//                     else entity.GetAttributes()[attrib.Key] = attrib.Value;
//                 }
//             }
//
//             if (speckleMeasurementsBase is not null)
//             {
//                 foreach (var measurement in speckleMeasurementsBase.GetMembers(DynamicBaseMemberType.Dynamic))
//                 {
//                     double? number = null;
//                     string? remark = null;
//             
//                     if (measurement.Value is IGH_Goo goo)
//                     {
//                         var gooValue = goo.GetType().GetProperty("Value")?.GetValue(goo);
//                         gooValue.TryConvertToDouble(out number, out remark);
//                     }
//                     else measurement.Value.TryConvertToDouble(out number, out remark);
//                 
//                     entity.GetMeasurements()[measurement.Key] = number;
//                     
//                     if (!number.HasValue)
//                     {
//                         this.AddRuntimeMessage(GH_RuntimeMessageLevel.Warning,
//                             string.Format(
//                                 "Warning: No value has been recorded for {0} as it is not a number: {1}",
//                                 measurement.Key,
//                                 remark));
//                     }
//                 }
//             }
//
//             DA.SetData(0, entity);
//         }
//     }
// }