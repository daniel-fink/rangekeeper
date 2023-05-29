using System;
using System.Collections.Generic;
using Grasshopper.Kernel;
using Speckle.Core.Models;
using Grasshopper.Kernel.Types;
using Speckle.Core.Kits;

namespace Rangekeeper;

public static class Extensions
{
    public static bool TryGetProperty(this Base baseObject, string propertyName, out object propertyValue)
    {
        propertyValue = null;
        if (baseObject.IsPropNameValid(propertyName, out string reason))
        {
            propertyValue = baseObject[propertyName];
            return true;
        }
        else return false;
    }

    public static bool CanConvertToBase(this IGH_Goo goo, ISpeckleConverter? converter, out Base? baseObject, out string? remark)
    {
        var value = goo.GetType().GetProperty("Value")?.GetValue(goo);
        if (value is Base)
        {
            baseObject = (Base)value;
            remark = null;
            return true;
        }
        else
        {
            try
            {
                baseObject = converter.ConvertToSpeckle(value);
                remark = "Input object was not a Speckle object, but has been converted to one.";
                return true;
            }
            catch (Exception e)
            {
                baseObject = null;
                remark = string.Format("Input object could not be converted to a Speckle Object. Error: {0}", e.Message);
                return false;
            }
        }
    }
}

