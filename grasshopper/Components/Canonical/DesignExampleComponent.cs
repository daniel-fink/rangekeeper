using System.Drawing;
using System.Text.Json.Nodes;
using System.Security.Cryptography;
using System.Text;
using System.Globalization;
using Grasshopper.Kernel;
using Rhino;
using Rhino.Geometry;
using Rhino.FileIO;
using Rangekeeper.Records;
using Rangekeeper.Serialization;
using ModelRecord=Rangekeeper.Records.Model;

namespace Rangekeeper.Components;

/// <summary>Example-specific geometry interpretation, outside the domain library.</summary>
public sealed class DesignExampleComponent : GH_Component
{
    public DesignExampleComponent():base("RK Example Design","Design","Read the preserved example 3dm and author canonical floor/utility records. No source changes, service calls or publication.","Rangekeeper","Examples"){}
    public override Guid ComponentGuid=>new("b2e45ba7-af08-4b49-9612-0d9308ced611");
    protected override Bitmap? Icon=>null;
    protected override void RegisterInputParams(GH_InputParamManager p)
    {
        p.AddTextParameter("Rhino source","File","Explicit exampleDesign.3dm path",GH_ParamAccess.item);
        p.AddNumberParameter("Floor elevations","Z","Explicit ascending elevations in metres, including one upper boundary",GH_ParamAccess.list);
    }
    protected override void RegisterOutputParams(GH_OutputParamManager p)
    {p.AddGenericParameter("Model","M","Authored Model with source evidence",GH_ParamAccess.item);p.AddTextParameter("Associations","A","External geometry associations",GH_ParamAccess.item);}
    protected override void SolveInstance(IGH_DataAccess data)
    {
        string path="";var levels=new List<double>();if(!data.GetData(0,ref path)||!data.GetDataList(1,levels))return;
        try { if(!Path.IsPathRooted(path))path=Path.Combine(Path.GetDirectoryName(OnPingDocument()?.FilePath) ?? throw new ArgumentException("Save the definition or supply an absolute Rhino source path"),path);var result=Build(path,levels);data.SetData(0,new RecordGoo(result.Model));data.SetData(1,result.Associations.ToJsonString()); }
        catch(Exception error){AddRuntimeMessage(GH_RuntimeMessageLevel.Error,error.Message);}
    }
    private static Guid Id(string key)
    {
        // Hash-derived UUIDs use stable source object IDs and declared coordinates,
        // never GH dispatch order or random generation on recompute.
        var bytes=SHA256.HashData(Encoding.UTF8.GetBytes("rk.example-design/v1:"+key)).Take(16).ToArray();
        bytes[7]=(byte)((bytes[7]&15)|0x80);bytes[8]=(byte)((bytes[8]&63)|0x80);return new Guid(bytes);
    }
    public static (ModelRecord Model,JsonArray Associations) Build(string path,IReadOnlyList<double> levels)
    {
        if(levels.Count<2 || levels.Any(z=>!double.IsFinite(z)) || !levels.SequenceEqual(levels.Distinct().OrderBy(z=>z)))throw new ArgumentException("Elevations must be finite, unique and ascending");
        using var file=File3dm.Read(path) ?? throw new ArgumentException("Cannot read Rhino source");
        if(file.Settings.ModelUnitSystem!=UnitSystem.Meters)throw new ArgumentException("This reviewed example requires metre geometry");
        var checksum=Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
        var revision=Id(checksum+":"+string.Join(",",levels.Select(z=>z.ToString("R",CultureInfo.InvariantCulture))));
        var source=Id("source:"+checksum);var classes=new JsonArray();var measures=new JsonArray();
        classes.Add(new JsonObject{["id"]=Id("class:design").ToString(),["code"]="design",["name"]="Design"});
        foreach(var kind in new[]{"property","building","space","floor","utilities","spatiallyContains","services","contains"})classes.Add(new JsonObject{["id"]=Id("class:"+kind).ToString(),["code"]=kind,["name"]=kind,["parent"]=Id("class:design").ToString()});
        foreach(var pair in new[]{("gfa","meter ** 2"),("perimeter","meter"),("ffl","meter"),("ftf","meter"),("volume","meter ** 3")})measures.Add(new JsonObject{["id"]=Id("measure:"+pair.Item1).ToString(),["code"]=pair.Item1,["name"]=pair.Item1,["units"]=pair.Item2});
        var entities=new JsonArray();var assemblies=new Dictionary<Guid,JsonObject>();var relationships=new JsonArray();var associations=new JsonArray();var claims=new JsonArray();var facts=new JsonArray();
        void Evidence(Guid target,string address,JsonNode content)
        {
            var claim=Id("claim:"+checksum+":"+target);
            claims.Add(new JsonObject{["id"]=claim.ToString(),["kind"]="sourced",["content"]=content.DeepClone(),["sources"]=new JsonArray(new JsonObject{["source"]=source.ToString(),["address"]=new JsonObject{["rhino_object_or_layer"]=address}})});
            facts.Add(new JsonObject{["target"]=target.ToString(),["claims"]=new JsonArray(claim.ToString())});
        }
        JsonObject Object(Guid uid,string name,string kind,bool assembly)
        {
            var obj=new JsonObject{["id"]=uid.ToString(),["name"]=name,["classification"]=Id("class:"+kind).ToString(),["characteristics"]=new JsonObject{["values"]=new JsonArray()}};
            if(assembly){obj["entities"]=new JsonArray();obj["relationships"]=new JsonArray();assemblies.Add(uid,obj);}else entities.Add(obj);
            Evidence(uid,name,new JsonObject{["name"]=name,["classification"]=kind});return obj;
        }
        void Quantity(JsonObject owner,string key,double magnitude,string unit,string address)
        {
            var uid=Id(owner["id"]+":"+key);var quantity=new JsonObject{["magnitude"]=magnitude,["units"]=unit};
            owner["characteristics"]!["values"]!.AsArray().Add(new JsonObject{["id"]=uid.ToString(),["key"]=key,["kind"]="measurement",["measure"]=Id("measure:"+key).ToString(),["quantity"]=quantity});Evidence(uid,address,quantity);
        }
        void Property(JsonObject owner,string key,string text,string kind="string")
        {
            var uid=Id(owner["id"]+":"+key);var content=new JsonObject{["kind"]=kind,["text"]=text};
            owner["characteristics"]!["values"]!.AsArray().Add(new JsonObject{["id"]=uid.ToString(),["key"]=key,["kind"]="property",["content"]=content});Evidence(uid,owner["name"]!.GetValue<string>(),content);
        }
        void Edge(Guid owner,Guid target,string kind)
        {
            var id=Id(owner+":"+kind+":"+target);var edge=new JsonObject{["id"]=id.ToString(),["source"]=owner.ToString(),["target"]=target.ToString(),["classification"]=Id("class:"+kind).ToString()};relationships.Add(edge);
            if(assemblies.TryGetValue(owner,out var group))
            {var members=group["entities"]!.AsArray();if(!members.Any(m=>m!.GetValue<string>()==target.ToString()))members.Add(target.ToString());group["relationships"]!.AsArray().Add(id.ToString());}
            Evidence(id,kind,edge);
        }
        void Associate(Guid domain,Guid geometry)=>associations.Add(new JsonObject{["model_revision"]=revision.ToString(),["domain_id"]=domain.ToString(),["rhino_id"]=geometry.ToString()});
        var root=Id("property");Object(root,"property","property",true);var utilityGroup=Id("utilities");Object(utilityGroup,"utilities","utilities",true);Edge(root,utilityGroup,"spatiallyContains");
        var buildings=new Dictionary<string,Guid>();var spaces=new Dictionary<string,List<Guid>>();var utilities=new List<(Guid Id,string Building,string Kind)>();
        // Rhino's file collection can expose empty/deleted slots through ICollection.
        // Enumerate and filter them before LINQ ordering copies the collection.
        foreach(var rhino in file.Objects.Where(o=>o is not null).OrderBy(o=>o.Id))
        {
            var layer=file.AllLayers.FindIndex(rhino.Attributes.LayerIndex);if(layer is null || !layer.FullPath.StartsWith("complex::",StringComparison.Ordinal))continue;
            var parts=layer.FullPath.Split(new[]{"::"},StringSplitOptions.None);if(parts.Length!=3)throw new ArgumentException("Unexpected example layer scope "+layer.FullPath);
            var building=parts[1];var use=parts[2];
            if(!buildings.ContainsKey(building)){var bid=Id("building:"+building);buildings.Add(building,bid);spaces.Add(building,new());Object(bid,building,"building",true);Edge(root,bid,"spatiallyContains");}
            var brep=rhino.Geometry is Extrusion extrusion?extrusion.ToBrep():rhino.Geometry as Brep;
            if(brep is null)throw new ArgumentException("Unsupported geometry on "+layer.FullPath);
            var type=rhino.Attributes.GetUserString("type");
            if(type=="utilities")
            {
                if(use is not ("plant" or "cores"))throw new ArgumentException("Unmapped utility use "+use);
                var uid=Id("object:"+rhino.Id);var owner=Object(uid,building+use,"utilities",false);
                using var volume=VolumeMassProperties.Compute(brep);if(volume is null)throw new ArgumentException("Utility volume unresolved");
                Quantity(owner,"volume",volume.Volume,"meter ** 3",rhino.Id.ToString());Property(owner,"use",use);Associate(uid,rhino.Id);
                Edge(buildings[building],uid,"spatiallyContains");Edge(utilityGroup,uid,"contains");utilities.Add((uid,building,use));
            }
            else if(type=="space")
            {
                var sid=Id("object:"+rhino.Id);var space=Object(sid,building+use,"space",true);Property(space,"use",use);Associate(sid,rhino.Id);spaces[building].Add(sid);Edge(buildings[building],sid,"spatiallyContains");
                using var spaceVolume=VolumeMassProperties.Compute(brep);
                if(spaceVolume is null)throw new ArgumentException("Space volume unresolved");
                Quantity(space,"volume",spaceVolume.Volume,"meter ** 3",rhino.Id.ToString());
                for(var i=0;i<levels.Count-1;i++)
                {
                    var curves=Brep.CreateContourCurves(brep,new Plane(new Point3d(0,0,levels[i]),Vector3d.ZAxis));if(curves is null || curves.Length==0)continue;
                    var surfaces=Brep.CreatePlanarBreps(Curve.JoinCurves(curves,.001),.001);if(surfaces is null)throw new ArgumentException("Contour is not a closed planar boundary");
                    for(var part=0;part<surfaces.Length;part++)
                    {
                        using var surface=surfaces[part];using var area=AreaMassProperties.Compute(surface);if(area is null)throw new ArgumentException("Floor area unresolved");
                        var fid=Id(rhino.Id+":floor:"+levels[i].ToString("R",CultureInfo.InvariantCulture)+":"+part);var floor=Object(fid,building+use+"Floor"+(i-2),"floor",false);
                        Quantity(floor,"gfa",area.Area,"meter ** 2",rhino.Id.ToString());Quantity(floor,"perimeter",surface.Edges.Sum(e=>e.GetLength()),"meter",rhino.Id.ToString());Quantity(floor,"ffl",levels[i],"meter",rhino.Id.ToString());Quantity(floor,"ftf",levels[i+1]-levels[i],"meter",rhino.Id.ToString());Property(floor,"number",(i-2).ToString(CultureInfo.InvariantCulture),"integer");Associate(fid,rhino.Id);Edge(sid,fid,"spatiallyContains");
                    }
                }
            }
            else throw new ArgumentException("Unmapped geometry type "+type);
        }
        foreach(var utility in utilities)
        {
            // The reviewed example routes plant to the two cores and plinth
            // spaces. Each core serves its building's spaces. The utilities
            // Assembly records this shared scope, not a spatial parent tree.
            var targets=utility.Kind=="plant"
                ? utilities.Where(u=>u.Kind=="cores").Select(u=>u.Id).Concat(spaces[utility.Building])
                : spaces[utility.Building].AsEnumerable();
            foreach(var target in targets)
            {
                Edge(utility.Id,target,"services");
                var group=assemblies[utilityGroup];var members=group["entities"]!.AsArray();
                if(!members.Any(m=>m!.GetValue<string>()==target.ToString()))members.Add(target.ToString());
                group["relationships"]!.AsArray().Add(Id(utility.Id+":services:"+target).ToString());
            }
        }
        var payload=new JsonObject{["metadata"]=new JsonObject{["id"]=revision.ToString(),["schema_version"]="0.6.0"},
            ["definitions"]=new JsonObject{["taxonomies"]=new JsonArray(new JsonObject{["id"]=Id("taxonomy").ToString(),["code"]="design",["name"]="Design",["classifications"]=classes}),["measures"]=measures},
            ["system"]=new JsonObject{["entities"]=entities,["assemblies"]=new JsonArray(assemblies.Values.Select(x=>(JsonNode)x).ToArray()),["relationships"]=relationships},
            ["provenance"]=new JsonObject{["sources"]=new JsonArray(new JsonObject{["id"]=source.ToString(),["name"]=Path.GetFileName(path),["checksum"]=checksum}),["claims"]=claims,["facts"]=facts}};
        var result=new ModelRecord(payload);Validation.Validator.Require(result);return(result,associations);
    }
}
