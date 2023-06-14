using System;
using System.Drawing;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Types;
using Speckle.Core.Models;

namespace Rangekeeper.Components
{
    public class CreateAssembly : GH_Component
    {
        public CreateAssembly()
            : base(
                "Create Rangekeeper Assembly",
                "CRkA",
                "Create a Rangekeeper Assembly",
                "Rangekeeper",
                "Entities"
            )
        { }

        // protected override Bitmap Icon => Resources.CreateAssemblyIcon;
        
        public override Guid ComponentGuid => new("F7297015-6047-4003-B205-D4918FE0A63A");
        
        protected override void RegisterInputParams(GH_InputParamManager pManager)
        {
            pManager.AddTextParameter(
                "Assembly Name",
                "N",
                "Name of the Assembly",
                GH_ParamAccess.item);
            pManager[0].Optional = true;
            
            pManager.AddTextParameter(
                "Type",
                "Ty",
                "Type of Assembly. (It is best to use a standardised vocabulary)",
                GH_ParamAccess.item);
            pManager[1].Optional = true;
        }
        
        protected override void RegisterOutputParams(GH_OutputParamManager pManager)
        {
            pManager.AddParameter(new AssemblyParam("Assembly", "A", "Rangekeeper Assembly", GH_ParamAccess.item));
        }
        
        protected sealed override void SolveInstance(IGH_DataAccess DA)
        {
            var name = string.Empty;
            DA.GetData(0, ref name);
            
            var type = string.Empty;
            DA.GetData(1, ref type);

            var assembly = new Assembly(name, type);

            DA.SetData(0, assembly);
        }
    }
}