"use strict";
(() => {
  const data = JSON.parse(document.getElementById("schema-data").textContent);
  const definitions = data.definitions;
  const $ = id => document.getElementById(id);
  const NS = "http://www.w3.org/2000/svg";
  const state = {scene:0, type:"Model", field:null, via:null, tab:"explain", mode:"forward", node:null};
  const W = 210, H = 108;
  const escape = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const fieldOf = (type,name) => definitions[type]?.fields?.find(f => f.name === name);
  const viaField = node => node.via ? fieldOf(...node.via.split(".")) : null;
  function constrainsField(value,field) {
    if (!value || typeof value !== "object") return false;
    if (value.slot_conditions && Object.hasOwn(value.slot_conditions,field)) return true;
    return Object.values(value).some(child=>constrainsField(child,field));
  }
  const conditionalRules = (type,field) => (definitions[type]?.raw.rules || []).filter(rule => constrainsField(rule.postconditions,field));
  const ranges = field => [...new Set([...(field.any_of || []).map(f => f.range), ...(field.all_of || []).map(f => f.range), ...(!field.any_of?.length ? [field.range] : [])].filter(Boolean))];
  function isInline(field, variant) {
    const chosen = variant ? (field.any_of || []).find(v => v.range === variant) : null;
    if (chosen && chosen.inlined !== undefined) return chosen.inlined;
    if (field.inlined !== undefined) return field.inlined;
    if (field.inlined_as_list) return true;
    const variants = field.any_of || field.all_of || [];
    return variants.length && variants.every(v => v.inlined === true);
  }
  const presence = (type,f) => conditionalRules(type,f.name).length ? "Conditional" : f.required ? "Required field" : "Optional field";
  function shape(f) {
    if (!f.multivalued) return "Single value";
    const explicit = f.minimum_cardinality != null || f.maximum_cardinality != null;
    return "Collection" + (explicit ? ` · ${f.minimum_cardinality ?? 0}..${f.maximum_cardinality ?? "*"} items` : "");
  }
  const textLink = (name,label=name) => definitions[name] ? `<button type="button" class="text-link" data-type="${escape(name)}">${escape(label)}</button>` : `<code>${escape(label)}</code>`;
  function svg(tag, attributes, text) {
    const element = document.createElementNS(NS, tag);
    for (const [key,value] of Object.entries(attributes || {})) element.setAttribute(key, value);
    if (text != null) element.textContent = text;
    return element;
  }
  function wrap(text, limit=29) {
    const lines = [""];
    for (const word of text.split(" ")) {
      const last = lines.length-1;
      if (lines[last] && lines[last].length + word.length + 1 > limit) lines.push(word);
      else lines[last] += (lines[last] ? " " : "") + word;
    }
    return lines;
  }
  function announce(message) { $("announcement").textContent = message; }
  function syncHash() {
    const params = new URLSearchParams({view:data.scenes[state.scene].id, record:state.type, tab:state.tab});
    if (state.field) params.set("field",state.field);
    if (state.via) params.set("via",state.via);
    if (state.mode === "inverse") params.set("example","inverse");
    try { history.replaceState(null,"","#"+params); } catch (_) { /* File hosts can restrict history. */ }
  }
  function select(type,field=null,via=null,node=null) {
    state.type=type; state.field=field; state.via=via; state.node=node; state.tab="explain";
    renderDetails(); highlight(); syncHash();
    announce((field ? type+"."+field : type)+" selected. Details updated.");
  }
  function edgePath(edge,nodes) {
    if (edge.path) return edge.path;
    const a=nodes[edge.from], b=nodes[edge.to];
    if (edge.side === "left") return [[a.x,a.y+H/2],[b.x+W,b.y+H/2]];
    if (edge.side === "bottom") return [[a.x+W/2,a.y+H],[b.x+W/2,b.y]];
    return [[a.x+W,a.y+H/2],[b.x,b.y+H/2]];
  }
  function drawGraph() {
    const scene=data.scenes[state.scene], graph=$("schema-graph");
    graph.replaceChildren(); graph.setAttribute("viewBox",`0 0 960 ${scene.height}`);
    graph.setAttribute("aria-label",scene.title+" Select a record or connection to read its schema.");
    const title=svg("title",{},scene.title);graph.append(title);
    const defs=svg("defs");
    const arrow=svg("marker",{id:"arrow",viewBox:"0 0 10 10",refX:9,refY:5,markerWidth:7,markerHeight:7,orient:"auto-start-reverse"});
    arrow.append(svg("path",{d:"M 0 1 L 9 5 L 0 9 Z",class:"graph-marker"}));defs.append(arrow);
    const diamond=svg("marker",{id:"diamond",viewBox:"0 0 12 10",refX:1,refY:5,markerWidth:10,markerHeight:8,orient:"auto"});
    diamond.append(svg("path",{d:"M 0 5 L 5 1 L 10 5 L 5 9 Z",class:"graph-marker"}));defs.append(diamond);
    const inherit=svg("marker",{id:"inherit",viewBox:"0 0 12 12",refX:11,refY:6,markerWidth:11,markerHeight:11,orient:"auto"});
    inherit.append(svg("path",{d:"M 1 1 L 11 6 L 1 11 Z",class:"graph-inherit"}));defs.append(inherit);graph.append(defs);
    const nodes=Object.fromEntries(scene.nodes.map(n=>[n.id,n]));
    for (const edge of scene.edges) {
      const owner=nodes[edge.from].type, field=edge.field ? fieldOf(owner,edge.field) : null;
      const points=edgePath(edge,nodes).map(p=>[...p]);
      const target=nodes[edge.to], targetField=viaField(target), last=points.at(-1), before=points.at(-2);
      if(targetField?.multivalued && last[1]===target.y && before[1]<last[1])last[1]-=10;
      if(targetField?.multivalued && last[0]===target.x+W && before[0]>last[0])last[0]+=10;
      const path="M "+points.map(p=>p.join(" ")).join(" L ");
      const group=svg("g",{class:"edge",role:"button",tabindex:0,"data-owner":owner,"data-field":edge.field || "", "aria-label":edge.kind === "inheritance" ? "Assembly is an Entity" : `${owner}.${edge.field}. ${field?.description || edge.semantic || "Read field contract"}`});
      const attrs={d:path,class:"line"};
      if (edge.kind === "inheritance") attrs["marker-end"]="url(#inherit)";
      else if (isInline(field,edge.variant) && !edge.semantic) attrs["marker-start"]="url(#diamond)";
      else attrs["marker-end"]="url(#arrow)";
      group.append(svg("path",attrs),svg("path",{d:path,class:"hit"}));
      const mid=edge.labelAt || [(points[0][0]+points.at(-1)[0])/2+ (edge.side === "bottom" ? 50 : 0),(points[0][1]+points.at(-1)[1])/2-12];
      group.append(svg("text",{x:mid[0],y:mid[1],"text-anchor":"middle",class:"edge-label"},edge.label || edge.field));
      const activate=()=>select(owner,edge.field || null);
      group.addEventListener("click",activate); group.addEventListener("keydown",event=>{if (["Enter"," "].includes(event.key)){event.preventDefault();activate();}});
      graph.append(group);
    }
    const compact=$("compact-graph");compact.replaceChildren();
    for (const node of scene.nodes) {
      const field=viaField(node), owner=node.via?.split(".")[0];
      const optional=field && !field.required, collection=field?.multivalued;
      const conditional=field && conditionalRules(owner,field.name).length;
      const unknown=scene.id === "example" && node.id === (state.mode === "forward" ? "cost" : "area");
      const group=svg("g",{class:"node"+(optional?" optional":"")+(unknown?" unknown":""),transform:`translate(${node.x} ${node.y})`,role:"button",tabindex:0,"data-node":node.id,"data-type":node.type,"aria-label":`${node.label || node.type}${collection?", collection":""}${optional?", optional field":""}${conditional?", conditional requirements":""}. ${node.caption}`});
      if(collection){group.append(svg("rect",{x:10,y:-10,width:W,height:H,rx:7}),svg("rect",{x:5,y:-5,width:W,height:H,rx:7}));}
      group.append(svg("rect",{x:0,y:0,width:W,height:H,rx:7,class:"front"}));
      let top = node.via ? node.via.split(".")[1] : definitions[node.type].category;
      if(conditional) top += " · conditional";
      else if(collection) top += top.length>9 ? " · many" : " · collection";
      group.append(svg("text",{x:16,y:22,class:"node-type"},top.toUpperCase()));
      group.append(svg("text",{x:16,y:49,class:"node-title"},node.label || node.type));
      const caption=wrap(node.caption);
      caption.slice(0,2).forEach((line,i)=>group.append(svg("text",{x:16,y:73+17*i,class:"node-caption"},line)));
      if(scene.id === "example" && ["area","rate","cost"].includes(node.id)) group.append(svg("text",{x:W/2,y:H+26,class:"example-role","text-anchor":"middle"},unknown?"UNKNOWN":"ASSIGNED"));
      const activate=()=>select(node.type,null,node.via || null,node.id);
      group.addEventListener("click",activate);group.addEventListener("keydown",event=>{if(["Enter"," "].includes(event.key)){event.preventDefault();activate();}});
      graph.append(group);
      const button=document.createElement("button");button.type="button";button.className="compact-node"+(optional?" optional":"");button.dataset.node=node.id;button.dataset.type=node.type;
      button.innerHTML=`<span class="compact-kind">${escape(top)}</span><strong>${escape(node.label || node.type)}</strong><span>${escape(node.caption)}${scene.id==="example" && ["area","rate","cost"].includes(node.id) ? " · "+(unknown?"unknown":"assigned") : ""}</span>`;
      button.addEventListener("click",activate);compact.append(button);
    }
    if(scene.id === "example") {
      graph.append(svg("text",{x:480,y:239,class:"example-equation","text-anchor":"middle"},"cost = area × rate"));
      graph.append(svg("text",{x:480,y:269,class:"example-detail","text-anchor":"middle"},state.mode === "forward" ? "1,000 m² × 2,000 AUD/m² = 2,000,000 AUD" : "2,000,000 AUD ÷ 2,000 AUD/m² = 1,000 m²"));
    }
    highlight();
  }
  function highlight() {
    const scene=data.scenes[state.scene];
    const selectedNode=state.node || scene.nodes.find(n=>n.type===state.type && (!state.via || n.via===state.via))?.id;
    document.querySelectorAll(".node,.compact-node").forEach(n=>{
      const selected=!state.field && n.dataset.node===selectedNode;
      n.classList.toggle("selected",selected);n.setAttribute("aria-pressed",String(selected));
    });
    document.querySelectorAll(".edge").forEach(e=>e.classList.toggle("selected",e.dataset.owner === state.type && e.dataset.field === state.field));
  }
  function renderScene(reset=true) {
    const scene=data.scenes[state.scene];
    if(reset){const first=scene.nodes[0];state.type=first.type;state.field=null;state.via=first.via || null;state.node=first.id;state.tab="explain";}
    $("scene-title").textContent=scene.title;$("scene-intro").textContent=scene.intro;$("takeaway").textContent=scene.takeaway;
    $("scene-index").textContent=`${String(state.scene+1).padStart(2,"0")} / ${String(data.scenes.length).padStart(2,"0")} · ${scene.label}`;
    $("step-count").textContent=`${state.scene+1} / ${data.scenes.length}`;
    $("previous").disabled=state.scene===0;$("next").disabled=state.scene===data.scenes.length-1;
    [...$("scene-nav").children].forEach((button,i)=>{if(i===state.scene)button.setAttribute("aria-current","step");else button.removeAttribute("aria-current");});
    $("example-controls").hidden=scene.id!=="example";
    drawGraph();renderDetails();syncHash();
  }
  function fieldList(item) {
    if(!item.fields?.length)return '<p class="empty-state">This definition has no record fields.</p>';
    return item.fields.map(f=>`<button type="button" class="field-button" data-field="${escape(f.name)}"><strong>${escape(f.name)}</strong><span>${escape(ranges(f).join(" | "))} · ${escape(presence(item.name,f))} · ${escape(shape(f))}</span>${f.description ? `<small>${escape(f.description)}</small>` : ""}</button>`).join("");
  }
  function ruleMarkup(rules) {
    if(!rules.length)return "";
    return `<h3>Conditional rules</h3><p class="source-note">Requirements depend on these conditions. Full rules are preserved below.</p>${rules.map((r,i)=>`<details><summary>${escape(r.description || "Rule "+(i+1))}</summary><pre>${escape(JSON.stringify(r,null,2))}</pre></details>`).join("")}`;
  }
  function renderField(item,f) {
    const rules=conditionalRules(item.name,f.name), rs=ranges(f);
    const modes=(f.any_of || [f]).filter(v=>definitions[v.range]?.category === "record").map(v=>`${v.range}: ${isInline(f,v.range)?"embedded record":"UUID reference"}`);
    const flags=[];
    if(f.identifier)flags.push("Identifier");if(f.key)flags.push("Collection key");if(f.list_elements_unique)flags.push("Unique items");if(f.list_elements_ordered)flags.push("Ordered items");
    return `<h3>Field definition</h3><p>${escape(f.description || "No field description is supplied in LinkML. Read its type definition and the containing record notes.")}</p><dl><dt>Range</dt><dd class="field-ranges">${rs.map(r=>textLink(r)).join(" <span>or</span> ")}</dd><dt>Presence</dt><dd>${escape(presence(item.name,f))}${rules.length ? ` · base declaration: ${f.required?"required":"optional"}` : ""}</dd><dt>Shape</dt><dd>${escape(shape(f))}</dd>${f.multivalued && f.minimum_cardinality == null && f.maximum_cardinality == null ? '<dt>Item count</dt><dd>No explicit minimum or maximum cardinality on this field.</dd>' : ""}${modes.length?`<dt>Storage</dt><dd>${modes.map(escape).join("<br>")}</dd>`:""}${flags.length?`<dt>Other constraints</dt><dd>${flags.map(escape).join(" · ")}</dd>`:""}${f.pattern?`<dt>Pattern</dt><dd><code>${escape(f.pattern)}</code></dd>`:""}</dl>${ruleMarkup(rules)}<h3>Containing record</h3><p>${textLink(item.name)}</p><p class="source-note">See the record notes for scope, ownership, and semantic requirements beyond this field's structural definition.</p>`;
  }
  function renderDetails() {
    const item=definitions[state.type];if(!item)return;
    const f=state.field ? fieldOf(state.type,state.field) : null;
    $("detail-category").textContent=f ? "Field contract" : (item.category === "record" ? "Record definition" : item.category+" definition");
    $("detail-title").textContent=f ? f.name : item.name;
    let context=f ? `<button type="button" class="context-link" data-type="${escape(item.name)}">${escape(item.name)}</button>` : item.parent ? `<span class="chip">is an ${escape(item.parent)}</span>` : `<span class="chip">${escape(item.source.split("/").at(-1))}</span>`;
    if(state.via && !f)context+=`<button type="button" class="context-link" data-via="${escape(state.via)}">via ${escape(state.via)}</button>`;
    $("detail-context").innerHTML=context;
    document.querySelectorAll("[data-tab]").forEach(b=>{b.setAttribute("aria-selected",String(b.dataset.tab===state.tab));b.tabIndex=b.dataset.tab===state.tab?0:-1;});
    $("detail-content").setAttribute("aria-labelledby","tab-"+state.tab);
    let content="";
    if(state.tab === "source") {
      content=`<h3>Original LinkML</h3><p class="source-note">${escape(item.source)}:${item.line} · module version ${escape(item.module_version)}</p><pre>${escape(item.yaml)}</pre>`;
      if(f)content+=`<h3>Resolved field</h3><p class="source-note">Includes inherited declarations and local slot overrides.</p><pre>${escape(JSON.stringify(f,null,2))}</pre>`;
    } else if(state.tab === "fields") {
      content=fieldList(item);
    } else if(f) {
      content=renderField(item,f);
    } else {
      if(item.parent)content+=`<div class="parent">Inherits from ${textLink(item.parent)}</div>`;
      if(state.via){const [owner,name]=state.via.split("."),slot=fieldOf(owner,name);if(slot)content+=`<p class="source-note">In this view: ${escape(presence(owner,slot))} · ${escape(shape(slot))}.</p>`;}
      content+=`<h3>Definition</h3><p>${escape(item.description || "No description is supplied in LinkML.")}</p>`;
      if(item.notes?.length)content+=`<h3>Notes from the schema</h3><ul>${item.notes.map(note=>`<li>${escape(note)}</li>`).join("")}</ul>`;
      if(item.category === "enum")content+=`<h3>Permitted values</h3>${Object.entries(item.raw.permissible_values || {}).map(([name,value])=>`<div class="enum-item"><code>${escape(name)}</code><p>${escape(value?.description || "")}</p></div>`).join("")}`;
      if(item.category === "type")content+=`<h3>Base type</h3><p>${escape(item.raw.typeof || "")}</p>${item.raw.pattern?`<h3>Pattern</h3><pre>${escape(item.raw.pattern)}</pre>`:""}`;
      content+=ruleMarkup(item.raw.rules || []);
      if(item.fields?.length)content+=`<h3>Explore fields</h3>${fieldList(item)}`;
    }
    $("detail-content").innerHTML=content;$("detail-content").scrollTop=0;
    $("detail-source").textContent=`${item.source}:${item.line} · module ${item.module_version}`;
    $("inspector").querySelectorAll("[data-type]").forEach(button=>button.addEventListener("click",()=>select(button.dataset.type)));
    $("inspector").querySelectorAll("[data-field]").forEach(button=>button.addEventListener("click",()=>select(item.name,button.dataset.field)));
    $("inspector").querySelectorAll("[data-via]").forEach(button=>button.addEventListener("click",()=>select(...button.dataset.via.split("."))));
  }
  function changeScene(index) {if(index<0 || index>=data.scenes.length)return;state.scene=index;renderScene();announce(data.scenes[index].title);}
  function openCatalogue() {$("catalogue").showModal();$("schema-search").value="";renderSearch();$("schema-search").focus();}
  function renderSearch() {
    const q=$("schema-search").value.trim().toLowerCase();
    const results=Object.values(definitions).filter(d=>!q || (d.name+" "+d.description+" "+d.source+" "+(d.notes || []).join(" ")).toLowerCase().includes(q)).sort((a,b)=>a.name.localeCompare(b.name));
    $("search-count").textContent=`${results.length} definitions`;
    $("search-results").innerHTML=results.map(d=>`<button type="button" data-type="${escape(d.name)}"><strong>${escape(d.name)}</strong><span class="result-kind">${d.category}</span><p>${escape(d.description.length>160 ? d.description.slice(0,157)+"…" : d.description)}</p></button>`).join("") || '<p class="empty-state">No definitions match this search.</p>';
    $("search-results").querySelectorAll("button").forEach(b=>b.addEventListener("click",()=>{
      const type=b.dataset.type;
      const i=data.scenes.findIndex(s=>s.nodes.some(n=>n.type===type));
      if(i>=0){state.scene=i;renderScene();}
      select(type);$("catalogue").close();$("detail-title").setAttribute("tabindex","-1");$("detail-title").focus();
    }));
  }
  data.scenes.forEach((scene,i)=>{const button=document.createElement("button");button.type="button";button.innerHTML=`<span class="nav-index">${String(i+1).padStart(2,"0")}</span>${escape(scene.label)}`;button.addEventListener("click",()=>changeScene(i));$("scene-nav").append(button);});
  document.querySelectorAll("[data-tab]").forEach((b,i,list)=>{
    b.addEventListener("click",()=>{state.tab=b.dataset.tab;renderDetails();syncHash();});
    b.addEventListener("keydown",e=>{if(["ArrowLeft","ArrowRight"].includes(e.key)){e.preventDefault();const next=list[(i+(e.key==="ArrowRight"?1:list.length-1))%list.length];next.click();next.focus();}});
  });
  $("previous").addEventListener("click",()=>changeScene(state.scene-1));$("next").addEventListener("click",()=>changeScene(state.scene+1));
  $("browse").addEventListener("click",openCatalogue);$("schema-search").addEventListener("input",renderSearch);
  $("notation").addEventListener("click",()=>$("notation-dialog").showModal());
  $("present").addEventListener("click",async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch(_){announce("Use your browser's full-screen command to present this page.");}});
  document.addEventListener("fullscreenchange",()=>{$("present").textContent=document.fullscreenElement?"Exit full screen":"Full screen";});
  document.addEventListener("keydown",e=>{
    if(document.querySelector("dialog[open]") || e.target.closest("input,textarea,select,button,[role='tab'],[role='button'],pre,summary") || e.ctrlKey || e.metaKey || e.altKey)return;
    if(e.key==="/"){e.preventDefault();openCatalogue();}
    if(e.key==="ArrowLeft"){e.preventDefault();changeScene(state.scene-1);}
    if(e.key==="ArrowRight"){e.preventDefault();changeScene(state.scene+1);}
  });
  ["forward","inverse"].forEach(mode=>$(mode).addEventListener("click",()=>{state.mode=mode;["forward","inverse"].forEach(m=>$(m).setAttribute("aria-pressed",String(m===mode)));drawGraph();syncHash();announce(mode==="forward"?"Find cost. Area and rate are assigned.":"Find area. Cost and rate are assigned.");}));
  const params=new URLSearchParams(location.hash.slice(1));
  const scene=data.scenes.findIndex(s=>s.id===params.get("view"));if(scene>=0)state.scene=scene;
  const type=params.get("record");if(type && definitions[type])state.type=type;else state.type=data.scenes[state.scene].nodes[0].type;
  if(fieldOf(state.type,params.get("field")))state.field=params.get("field");
  if(["explain","fields","source"].includes(params.get("tab")))state.tab=params.get("tab");
  const via=params.get("via");if(via && fieldOf(...via.split(".")))state.via=via;
  if(params.get("example")==="inverse"){state.mode="inverse";$("forward").setAttribute("aria-pressed","false");$("inverse").setAttribute("aria-pressed","true");}
  $("version").textContent=`Model schema ${data.model_version}`;
  $("snapshot").textContent=`${data.modules.length} LinkML modules · source ${data.schema_hash.slice(0,12)}`;
  $("snapshot").title=`SHA-256 of source schema and bundle: ${data.schema_hash}`;
  renderScene(false);
})();
