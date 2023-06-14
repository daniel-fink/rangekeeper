using System;
using System.Collections.Generic;
using System.Dynamic;
using System.Runtime.CompilerServices;
using Grasshopper.Kernel;
using Speckle.Core.Models;
using Grasshopper.Kernel.Types;
using Microsoft.CSharp.RuntimeBinder;
using Speckle.Core.Kits;

using Speckle.Newtonsoft.Json;

namespace Rangekeeper;

public static class Extensions
{
    public static bool TryGetProperty(this Base speckleBase, string propertyName, out object? property, out string? remark)
    {
        var members = speckleBase.GetMembers();
        if (members.ContainsKey(propertyName))
        {
            property = speckleBase[propertyName];
            remark = null;
            return true;
        }
        else
        {
            property = null;
            remark = string.Format("{0} property not found in Speckle Object", propertyName);
            return false;
        }
    }

    public static bool TryConvertToDecimal(this object obj, out decimal? number, out string? remark)
    {
        try
        {
            number = Convert.ToDecimal(obj);
            remark = null;
            return true;
        }
        catch (Exception e)
        {
            number = null;
            remark = string.Format("Could not convert {0} (of type {1}) to Decimal: {2}", obj, obj.GetType(), e.Message);
            return false;
        }
    }
    
    public static bool TryConvertToDouble(this object obj, out double? number, out string? remark)
    {
        try
        {
            number = Convert.ToDouble(obj);
            remark = null;
            return true;
        }
        catch (Exception e)
        {
            number = null;
            remark = string.Format("Could not convert {0} (of type {1}) to Double: {2}", obj, obj.GetType(), e.Message);
            return false;
        }
    }

    public static bool CanConvertToBase(this IGH_Goo goo, out Base? speckleBase, out string? remark)
    {
        if (goo is null)
        {
            speckleBase = null;
            remark = "Input object was null";
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
                remark = "Input object was not a Speckle Object";
                return false;
            }
        }
    }
    
    public static bool CanConvertToEntity(this IGH_Goo goo, out IEntity? entity, out string? remark)
    {
        var value = goo.GetType().GetProperty("Value")?.GetValue(goo);
        if (value is IEntity baseEntity)
        {
            entity = baseEntity;
            remark = null;
            return true;
        }
        else
        {
            entity = null;
            remark = string.Format("Input object was not a Rangekeeper Entity");
            return false;
        }
    }
    
    public static decimal? ToNullableDecimal(this object? obj)
    {
        if (obj is null) return null;
        else return Convert.ToDecimal(obj);
    }
    
    /// <summary>
    /// Perform a deep Copy of the object, using Json as a serialization method. 
    /// Note: Private members are not cloned using this method.
    /// </summary>
    public static T CloneViaSerialization<T>(this T source)
    {
        // Don't serialize a null object, simply return the default for that object
        if (ReferenceEquals(source, null))
        {
            return default(T);
        }

        // initialize inner objects individually
        // for example in default constructor some list property initialized with some values,
        // but in 'source' these items are cleaned -
        // without ObjectCreationHandling.Replace default constructor values will be added to result
        var deserializeSettings = new JsonSerializerSettings { ObjectCreationHandling = ObjectCreationHandling.Replace };

        return JsonConvert.DeserializeObject<T>(JsonConvert.SerializeObject(source), deserializeSettings);
    }
}

