using System;
using System.Drawing;
using Grasshopper.Kernel;
using RangekeeperGrasshopper;

namespace Rangekeeper.Components;

public class AssemblyParam : GH_Param<GH_Assembly>
{
    // public bool IsSchemaBuilderOutput;

    // public bool UseSchemaTag;

    public AssemblyParam(
        string name,
        string nickname,
        string description,
        GH_ParamAccess access,
        bool isSchemaBuilderOutput = false
    )
        : this(name, nickname, description, "Params", "Primitive", access)
    {
        // IsSchemaBuilderOutput = isSchemaBuilderOutput;
    }

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
        "RKA",
        "Rangekeeper Assembly, derived from a Speckle Collection",
        GH_ParamAccess.item) 
    { }

    public override Guid ComponentGuid => new("6B901C91-6C3D-40E1-803D-C9226A58A4BB");
    protected override Bitmap Icon => Resources.AssemblyParamIcon;
    public override GH_Exposure Exposure => GH_Exposure.tertiary;

    // public override GH_StateTagList StateTags
    // {
    //     get
    //     {
    //         var tags = base.StateTags;
    //         if (Kind != GH_ParamKind.output)
    //             return tags;
    //         if (!IsSchemaBuilderOutput)
    //             return tags;
    //         // if (UseSchemaTag)
    //         //     tags.Add(new SchemaTagStateTag());
    //
    //         return tags;
    //     }
    // }
}