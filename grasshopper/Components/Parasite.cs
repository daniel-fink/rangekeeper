//using System;
//using System.Collections.Generic;
//using System.IO;
//using System.Linq;

//using Grasshopper.Kernel;
//using Grasshopper.Kernel.Special;
//using Grasshopper.GUI.Script;

////using ScriptComponents;


//// In order to load the result of this wizard, you will also need to
//// add the output bin/ folder of this project to the list of loaded
//// folder in Grasshopper.
//// You can use the _GrasshopperDeveloperSettings Rhino command for that.

//namespace Rangekeeper.Components
//{
//    public class ParasiteComponent : GH_Component
//    {
//        private int _iteration;
//        protected Component_CSNET_Script TargetComponent { get; set; }

//        /// <summary>
//        /// Each implementation of GH_Component must provide a public 
//        /// constructor without any arguments.
//        /// Category represents the Tab in which the component will appear, 
//        /// Subcategory the panel. If you use non-existing tab or panel names, 
//        /// new tabs/panels will automatically be created.
//        /// </summary>
//        public ParasiteComponent(): base
//            (
//            "Parasite",
//            "Parasite",
//            "Parasite injects a text file into a Grasshopper C# scripting component, complete with custom 'using', 'script', and 'additional' code sections.",
//            "Maths",
//            "Script"
//            )
//        {
//            this.Message = "Unconnected";
//        }
        

//        /// <summary>
//        /// Registers all the input parameters for this component.
//        /// </summary>
//        protected override void RegisterInputParams(GH_Component.GH_InputParamManager pManager)
//        {
//            pManager.AddTextParameter("File", "F", "Path to the code file. Use the FilePath parameter with the Syncronize option enabled.", GH_ParamAccess.item);
//        }

//        /// <summary>
//        /// Registers all the output parameters for this component.
//        /// </summary>
//        protected override void RegisterOutputParams(GH_Component.GH_OutputParamManager pManager)
//        {
//        }

//        protected override void BeforeSolveInstance()
//        {
//            _iteration = 0;
//        }

//        /// <summary>
//        /// This is the method that actually does the work.
//        /// </summary>
//        /// <param name="DA">The DA object can be used to retrieve data from input parameters and 
//        /// to store data in output parameters.</param>
//        protected override void SolveInstance(IGH_DataAccess da)
//        {
//            // reset everything, and let's start over..
//            // things are botched up if this script runs more than once.
//            if (_iteration++ != 0) return;

//            string filePath = string.Empty;
//            da.GetData(0, ref filePath);

//            // Find the scripts in the current group.
//            var scripts = FindObjectsOfTypeInCurrentGroup<Component_CSNET_Script>();
//            if (scripts.Count != 1)
//            {
//                this.Message = "Error";
//                AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, "This component should be added in a group with exactly one C# script.");
//                return;
//            }

//            this.TargetComponent = scripts.FirstOrDefault();
//            this.Message = this.TargetComponent.NickName;

//            try
//            {
//                string inputCode;
//                using (StreamReader streamReader = new StreamReader(filePath))
//                {
//                    inputCode = streamReader.ReadToEnd();
//                }

//                if (this.TargetComponent != null)
//                {
//                    this.TargetComponent.SourceCodeChanged(new GH_ScriptEditor(GH_ScriptLanguage.CS));
//                    var splitLines = new List<string>();
//                    splitLines.Add("#region CustomUsing");
//                    splitLines.Add("#endregion CustomUsing");

//                    splitLines.Add("#region CustomScript");
//                    splitLines.Add("#endregion CustomScript");

//                    splitLines.Add("#region CustomAdditional");
//                    splitLines.Add("#endregion CustomAdditional");

//                    string[] inputs = inputCode.Split(splitLines.ToArray(), StringSplitOptions.None);
//                    this.TargetComponent.ScriptSource.UsingCode = inputs[1];
//                    this.TargetComponent.ScriptSource.ScriptCode = inputs[3];
//                    this.TargetComponent.ScriptSource.AdditionalCode = inputs[5];

//                    this.TargetComponent.ExpireSolution(true);
//                }
//            }
//            catch (Exception e)
//            {
//                this.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, e.Message);
//            }
//        }

//        /// <summary>
//        /// Provides an Icon for every component that will be visible in the User Interface.
//        /// Icons need to be 24x24 pixels.
//        /// </summary>
//        protected override System.Drawing.Bitmap Icon
//        {
//            get
//            {
//                // You can add image files to your project resources and access them like this:
//                return Resources.ParasiteIcon;
//            }
//        }

//        /// <summary>
//        /// Each component must have a unique Guid to identify it. 
//        /// It is vital this Guid doesn't change otherwise old ghx files 
//        /// that use the old ID will partially fail during loading.
//        /// </summary>
//        public override Guid ComponentGuid
//        {
//            get { return new Guid("bf6214b8-736a-4eb4-b0e1-8e11150f705d"); }
//        }

//        /// <summary>
//        /// Find all objects of type T in any group this current script instance is a member of.
//        /// </summary>
//        /// <typeparam name="T"></typeparam>
//        /// <returns>A list of objects of type T that belong to group T</returns>
//        private List<T> FindObjectsOfTypeInCurrentGroup<T>() where T : IGH_ActiveObject
//        {
//            // find all groups that this object is in.
//            var groups = OnPingDocument()
//                .Objects
//                .OfType<GH_Group>()
//                .Where(gr => gr.ObjectIDs.Contains(InstanceGuid))
//                .ToList();

//            // find in the groups that this object is in all objects of type T.
//            var output = groups.Aggregate(new List<T>(), (list, item) =>
//            {
//                list.AddRange(
//                    OnPingDocument().Objects.OfType<T>()
//                        .Where(obj => item.ObjectIDs.Contains(obj.InstanceGuid))
//                );
//                return list;
//            }).Distinct().ToList();

//            return output;
//        }
//    }

//    public class ParasiteExtensions
//    {

//    }
//}
