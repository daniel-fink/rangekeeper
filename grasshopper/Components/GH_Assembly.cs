using Grasshopper.Kernel.Types;
using Speckle.Core.Models;
using Speckle.Core.Models.Extensions;

namespace Rangekeeper.Components;

public class GH_Assembly : GH_Goo<Assembly>
{
    public override IGH_Goo Duplicate() => new GH_Assembly() { m_value = m_value.Clone() };

    public override string ToString() 
    {
        object? name;
        if (!this.Value.TryGetProperty("name", out name, out string? remark)) name = "[Unnamed]";
        return string.Format("Rangekeeper Assembly [{0}]", name);
    }

    public override bool IsValid => m_value != null;
    
    public override string TypeName => "Rangekeeper Assembly";

    public override string TypeDescription => "Represents a Rangekeeper Assembly of related Entities";

    public override bool CastFrom(object source)
    {
        switch (source)
        {
            case Assembly assembly:
                Value = assembly;
                return true;
            case GH_Assembly gooAssembly:
                Value = gooAssembly.Value;
                return true;
            case GH_Goo<Base> goo:
                if (goo.Value is Assembly gooBaseAssembly)
                {
                    Value = gooBaseAssembly;
                    return true;
                }
                break;
        }
        return false;
    }

    public override bool CastTo<Q>(ref Q target)
    {
        var success = false;
        var type = typeof(Q);
        
        if (type == typeof(IEntity))
        {
            target = (Q)(object)this.Value;
            success = true;
        }
        
        else if (type == typeof(Entity))
        {
            target = (Q)(object)this.Value;
            success = true;
        }
        
        else if (type == typeof(Assembly))
        {
            target = (Q)(object)this.Value;
            success = true;
        }
        
        else if (type == typeof(GH_Entity))
        {
            target = (Q)(object)new GH_Entity() { Value = this.Value };
            success = true;
        }
        
        else if (type == typeof(GH_Assembly))
        {
            target = (Q)(object)new GH_Assembly { Value = Value };
            success = true;
        }
        
        else if (type == typeof(GH_Goo<Base>))
        {
            target = (Q)(object)(Base)this.Value;
            success = true;
        }

        return success;
    }
}