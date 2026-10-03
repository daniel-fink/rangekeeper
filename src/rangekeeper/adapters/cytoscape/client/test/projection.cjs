const {test} = require('node:test');
const assert = require('node:assert/strict');
const {projectCollapse} = require('../../assets/projection.cjs');
const nodes = ['apt','hvac','room','ahu','plant','isolated'].map(id => ({data:{id}}));
const edge = (id,source,target,type='services') => ({data:{id,source,target,type,label:type}});
const graph = {elements:[...nodes,edge('a','ahu','room'),edge('b','plant','ahu'),edge('c','ahu','plant','connected'),edge('d','plant','room'),edge('e','plant','room','connected'),edge('f','room','plant'),edge('g','hvac','room')],assemblies:{apt:{entities:['room','ahu']},hvac:{entities:['ahu','plant']}}};
const summary = p => p.edges.filter(e=>e.connector==='summary');
test('all four shared-member states retain canonical identity and memberships',()=>{
  const copy=JSON.stringify(graph);
  assert.deepEqual(projectCollapse(graph,[]).hiddenIds,[]);
  assert.deepEqual(projectCollapse(graph,['hvac']).hiddenIds,['plant']);
  assert.deepEqual(projectCollapse(graph,['apt']).hiddenIds,['room']);
  assert.deepEqual(projectCollapse(graph,['apt','hvac']).hiddenIds,['ahu','plant','room']);
  assert.equal(JSON.stringify(graph),copy);
});
test('membership links exist only for visible members of collapsed Assemblies',()=>{
  const p=projectCollapse(graph,['hvac']);
  assert.deepEqual(p.edges.filter(e=>e.connector==='membership').map(e=>[e.source,e.target]),[['ahu','hvac']]);
  assert.equal(projectCollapse(graph,['apt','hvac']).edges.filter(e=>e.connector==='membership').length,0);
});
test('summaries preserve direction, mix labels and suppress internal connections',()=>{
  const p=projectCollapse(graph,['hvac']);
  const s=summary(p).find(e=>e.source==='hvac'&&e.target==='room');
  assert.equal(s.label,'Relationships');assert.deepEqual(s.originalIds,['d','e']);
  assert.ok(summary(p).some(e=>e.source==='room'&&e.target==='hvac'));
  assert.ok(p.edges.some(e=>e.id==='g'&&e.connector==='domain'));
  assert.ok(summary(p).every(e=>e.source!==e.target));
});
test('opposite collapse orders yield identical, unique projected edges',()=>{
  const a=projectCollapse(graph,['apt','hvac']),b=projectCollapse(graph,['hvac','apt']);
  assert.deepEqual(a,b);assert.equal(new Set(a.edges.map(e=>e.id)).size,a.edges.length);
  for(const e of summary(a))assert.equal(new Set(e.originalIds).size,e.originalIds.length);
});
test('filtered originals determine summary label and evidence',()=>{
  const p=projectCollapse(graph,['hvac'],new Set(['services']));
  const s=summary(p).find(e=>e.source==='hvac'&&e.target==='room');
  assert.equal(s.label,'services');assert.deepEqual(s.originalIds,['d']);
  assert.ok(p.edges.some(e=>e.connector==='membership'));
});
test('one redirected relationship is still a summary; original edges stay original',()=>{
  const p=projectCollapse(graph,['hvac']);
  assert.deepEqual(summary(p).find(e=>e.source==='hvac'&&e.target==='ahu').originalIds,['b']);
  assert.equal(p.edges.find(e=>e.id==='a').connector,'domain');
});
