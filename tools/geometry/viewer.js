import { Viewer, DefaultViewerParams, CameraController, SelectionExtension, FilteringExtension, SpeckleLoader, ViewerEvent } from '@speckle/viewer';
import { ObjectLoader2Factory } from '@speckle/objectloader2';

// The SDK's offline loader is a stub in 2.31.14. Supply the documented
// in-memory ObjectLoader factory; Speckle still converts and renders the source.
class PinnedSourceLoader extends SpeckleLoader {
  initObjectLoader(resource, token, cache, records) {
    if (!records?.length) throw new Error('The source archive is empty');
    return ObjectLoader2Factory.createFromObjects(records);
  }
}
const status = document.querySelector('#status');
const objects = document.querySelector('#objects');
const properties = document.querySelector('#properties');
const isolate = document.querySelector('#isolate');
let rootId;
const buttons = [...document.querySelectorAll('button')];
buttons.forEach(button => button.disabled = true);

async function load() {
  const config = await (await fetch('geometry.json')).json();
  rootId = config.rootId;
  const loadAsset = async name => {
    const response = await fetch(config.data + '/' + name);
    if (!response.ok) throw new Error(name + ': HTTP ' + response.status);
    const bytes = await response.arrayBuffer();
    const hash = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(x => x.toString(16).padStart(2, '0')).join('');
    if (hash !== config.files[name]) throw new Error(name + ': checksum mismatch');
    return bytes;
  };
  const compressed = await loadAsset('transport.json.gz');
  const associations = JSON.parse(new TextDecoder().decode(await loadAsset('associations.json')));
  const model = JSON.parse(new TextDecoder().decode(await loadAsset('model.json')));
  const domainIds = new Set([...(model.system?.entities || []), ...(model.system?.assemblies || []), ...(model.system?.relationships || [])].map(o => o.id));
  if (model.metadata.id !== config.modelId || associations.some(a => a.model_revision !== config.modelId || !domainIds.has(a.domain_id))) throw new Error('Stale or unknown geometry association');
  const domainBySource = new Map(associations.map(a => [a.content_id, a.domain_id]));
  const text = await new Response(new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip'))).text();
  const transport = JSON.parse(text);
  if (!transport[rootId]) throw new Error('Pinned root is missing');
  const records = [JSON.parse(transport[rootId]), ...Object.entries(transport).filter(([id]) => id !== rootId).map(([, record]) => JSON.parse(record))];
  const viewer = new Viewer(document.querySelector('#scene'), { ...DefaultViewerParams, verbose: false, showStats: false });
  await viewer.init();
  viewer.setLightConfiguration({ castShadow: false });
  const camera = viewer.createExtension(CameraController);
  const selection = viewer.createExtension(SelectionExtension);
  const filtering = viewer.createExtension(FilteringExtension);
  const loaded = await viewer.loadObject(new PinnedSourceLoader(viewer.getWorldTree(), 'pinned-property', undefined, false, records), true);
  if (loaded === false) throw new Error('Speckle could not render the source');
  const tree = viewer.getWorldTree();
  const nodes = tree.findAll(node => domainBySource.has(node.model.id));
  const byDomain = new Map();
  for (const node of nodes) {
    const id = domainBySource.get(node.model.id);
    if (!byDomain.has(id)) byDomain.set(id, []);
    byDomain.get(id).push(node);
  }
  const physical = nodes.filter(node => node.model.raw.type === 'floor' || ['plant', 'cores'].includes(node.model.raw.use));
  const idsFor = view => (view === 'floors' ? physical.filter(node => node.model.raw.type === 'floor') : view === 'utilities' ? physical.filter(node => ['plant','cores'].includes(node.model.raw.use)) : physical).map(node => node.model.id);
  const palette = { hotel: '#4477AA', residential: '#228833', retail: '#CCBB44', parking: '#999999', cores: '#AA3377', plant: '#EE6677' };
  const colourGroups = Object.entries(palette).map(([use, color]) => ({
    color,
    objectIds: physical.filter(node => {
      const own = node.model.raw.use;
      const inherited = tree.getAncestors(node).find(parent => parent.model.raw?.use)?.model.raw.use;
      return (own || inherited) === use;
    }).map(node => node.model.id),
  })).filter(group => group.objectIds.length);
  function colourObjects(visibleIds) {
    const allowed = visibleIds && new Set(visibleIds);
    const groups = colourGroups.map(group => ({ ...group, objectIds: group.objectIds.filter(id => {
      if (!allowed || allowed.has(id)) return true;
      return tree.findId(id)?.some(node => tree.getAncestors(node).some(parent => allowed.has(parent.model.id)));
    }) })).filter(group => group.objectIds.length);
    filtering.setUserObjectColors(groups);
  }
  let currentView = 'context';
  let selectedIds = [];
  function showView(view) {
    currentView = view;
    selectedIds = []; objects.value = ''; isolate.disabled = true;
    properties.textContent = 'Select geometry or choose an object.';
    selection.clearSelection();
    filtering.resetFilters();
    const ids = view === 'context' ? undefined : idsFor(view);
    colourObjects(ids);
    if (ids) filtering.isolateObjects(ids, undefined, true, false);
    camera.setCameraView(ids, true);
    document.querySelectorAll('[data-view]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.view === view)));
    status.textContent = `${view === 'context' ? 'Whole design and context' : view[0].toUpperCase() + view.slice(1)} · captured 12 October 2026 · local source`;
  }
  const keys = { name: 'Name', type: 'Type', use: 'Use', number: 'Floor number', gfa: 'GFA (m²)', perimeter: 'Perimeter (m)', ftf: 'Floor-to-floor (m)', ffl: 'Elevation (m)', volume: 'Volume (m³)', entityId: 'Rangekeeper identity', id: 'Source content ID' };
  function inspect(node) {
    const ancestors = tree.getAncestors(node);
    const domain = [node, ...ancestors.slice().reverse()].find(item => item.model.raw?.entityId);
    const raw = (domain || node).model.raw;
    selectedIds = domain ? byDomain.get(raw.entityId).map(item => item.model.id) : [node.model.id];
    selection.selectObjects(selectedIds);
    objects.value = raw.entityId || '';
    const dl = document.createElement('dl');
    for (const [key, title] of Object.entries(keys)) {
      if (raw[key] === undefined || raw[key] === null) continue;
      const dt = document.createElement('dt'); dt.textContent = title;
      const dd = document.createElement('dd'); dd.textContent = typeof raw[key] === 'number' ? raw[key].toLocaleString(undefined, { maximumFractionDigits: 3 }) : String(raw[key]);
      dl.append(dt, dd);
    }
    properties.replaceChildren(dl);
    isolate.disabled = false;
    currentView = 'selection';
    document.querySelectorAll('[data-view]').forEach(button => button.setAttribute('aria-pressed', 'false'));
    status.textContent = `Selected: ${raw.name || raw.id} · local source`;
  }
  for (const [id, entries] of [...byDomain].sort((a,b) => a[1][0].model.raw.name.localeCompare(b[1][0].model.raw.name))) {
    const option = document.createElement('option'); option.value = id; option.textContent = entries[0].model.raw.name; objects.append(option);
  }
  objects.addEventListener('change', () => { const node = byDomain.get(objects.value)?.[0]; if (node) { filtering.resetFilters(); colourObjects(); inspect(node); camera.setCameraView(selectedIds, true); } });
  viewer.on(ViewerEvent.ObjectClicked, event => { if (event?.hits?.length) inspect(event.hits[0].node); });
  document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => showView(button.dataset.view)));
  document.querySelector('#fit').addEventListener('click', () => camera.setCameraView(currentView === 'context' ? undefined : currentView === 'selection' ? selectedIds : idsFor(currentView), true));
  document.querySelector('#top').addEventListener('click', () => camera.setCameraView('top', true));
  isolate.addEventListener('click', () => { colourObjects(selectedIds); filtering.isolateObjects(selectedIds, undefined, true, false); camera.setCameraView(selectedIds, true); });
  buttons.forEach(button => button.disabled = false); isolate.disabled = true; objects.disabled = false;
  const view = new URLSearchParams(location.search).get('view');
  showView(['context','property','floors','utilities'].includes(view) ? view : 'property');
}
load().catch(error => { status.textContent = `Viewer unavailable: ${error.message}. Use the still image in the chapter.`; status.style.color = '#aa2233'; console.error(error); });
