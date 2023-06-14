using System;
using System.Drawing;
using Grasshopper.Kernel;

namespace Rangekeeper.Components;

public class AssemblyParam : GH_Param<GH_Assembly>
{
    public AssemblyParam(
        string name,
        string nickname,
        string description,
        GH_ParamAccess access
    )
        : this(name, nickname, description, "Params", "Primitive", access)
    { }

    public AssemblyParam(
        string name,
        string nickname,
        string description,
        string category,
        string subcategory,
        GH_ParamAccess access
    )
        : base(name, nickname, description, category, subcategory, access) { }

    public AssemblyParam() : this(
        "Rangekeeper Assembly Object",
        "RKkA",
        "Rangekeeper Assembly, encapsulating Entities and extending a Speckle Object",
        GH_ParamAccess.item) 
    { }

    public override Guid ComponentGuid => new("8C4EB9A5-A658-49B9-B1E8-3982A524CAE2");
    
    // protected override Bitmap Icon => Resources.AssemblyParamIcon;
    
    public override GH_Exposure Exposure => GH_Exposure.tertiary;
    
}