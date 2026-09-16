const {test}=require('node:test');
const assert=require('node:assert/strict');
const {projectCollapse}=require('../../assets/projection.cjs');
const nodes=['building','left','right','shared','private','outside'].map(id=>({data:{id}}));
const edge=(id,source,target)=>({data:{id,source,target,type:'service',label:'Services'}});
const graph={elements:[...nodes,edge('a','private','outside'),edge('b','shared','outside')],assemblies:{building:{entities:['left'],relationships:[]},left:{entities:['private','shared'],relationships:[]},right:{entities:['shared'],relationships:[]}}};
test('collapsed ancestor hides private descendants but preserves another open membership path',()=>{
 const p=projectCollapse(graph,['building']);assert.deepEqual(p.hiddenIds,['left','private']);
 assert.ok(p.edges.some(e=>e.connector==='membership'&&e.source==='shared'&&e.target==='building'));
 assert.deepEqual(p.edges.find(e=>e.connector==='summary').originalIds,['a']);
});
test('all containing paths collapsed hides shared once and retains both directed representatives',()=>{
 const p=projectCollapse(graph,['building','right']);assert.deepEqual(p.hiddenIds,['left','private','shared']);
 const s=p.edges.filter(e=>e.connector==='summary');assert.equal(s.length,2);
 assert.deepEqual(s.find(e=>e.source==='building').originalIds,['a','b']);
 assert.deepEqual(s.find(e=>e.source==='right').originalIds,['b']);
 assert.deepEqual(p,projectCollapse(graph,['right','building']));
});
test('expanding ancestor preserves explicitly collapsed descendant state',()=>{
 assert.deepEqual(projectCollapse(graph,['building','left']).hiddenIds,['left','private']);
 assert.deepEqual(projectCollapse(graph,['left']).hiddenIds,['private']);
 assert.deepEqual(projectCollapse(graph,[]).hiddenIds,[]);
});
test('membership cycles fail explicitly rather than recursing forever',()=>{
 const cyclic=structuredClone(graph);cyclic.assemblies.left.entities.push('building');
 assert.throws(()=>projectCollapse(cyclic,[]),/cycle/);
});
