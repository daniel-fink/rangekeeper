using System;
using System.Drawing;
using Grasshopper.Kernel;

namespace Rangekeeper.Components;

public class EntityParam : GH_Param<GH_Entity>
{
    public EntityParam(
        string name,
        string nickname,
        string description,
        GH_ParamAccess access
    )
        : base(name, nickname, description, "Params", "Primitive", access)
    { }

    public EntityParam(
        string name,
        string nickname,
        string description,
        string category,
        string subcategory,
        GH_ParamAccess access
    )
        : base(name, nickname, description, category, subcategory, access) { }

    public EntityParam() : this(
        "Rangekeeper Entity Object",
        "RkE",
        "Rangekeeper Entity, extending a Speckle Object",
        GH_ParamAccess.item) 
    { }

    public override Guid ComponentGuid => new("8316B1CC-A04B-4276-85B9-C0A987A9F6BD");
    
    // protected override Bitmap Icon => Resources.EntityParamIcon;
    
    public override GH_Exposure Exposure => GH_Exposure.tertiary;
}