using Grasshopper.Kernel.Types;
using Speckle.Core.Models;

namespace Rangekeeper.Components;

public static class Extensions
{
    public static bool CanConvertToBase(this IGH_Goo? goo, out Base? speckleBase, out string? remark)
    {
        if (goo is null)
        {
            speckleBase = null;
            remark = "Input Object was null";
            return false;
        }
        else
        {
            var value = goo.GetType().GetProperty("Value")?.GetValue(goo);
            if (value is Base baseObject)
            {
                speckleBase = baseObject;
                remark = null;
                return true;
            }
            else
            {
                speckleBase = null;
                remark = "Input Object was not a Speckle Object";
                return false;
            }
        }
    }
    
    public static bool CanConvertToEntity(this IGH_Goo goo, out IEntity? ientity, out string? remark)
    {
        var value = goo.GetType().GetProperty("Value")?.GetValue(goo);
        if (value is Entity baseEntity)
        {
            ientity = baseEntity;
            remark = null;
            return true;
        }
        else
        {
            ientity = null;
            remark = string.Format("Input object was not a Rangekeeper Entity");
            return false;
        }
    }
}





