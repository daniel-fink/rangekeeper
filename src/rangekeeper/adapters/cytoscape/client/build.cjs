const esbuild = require('esbuild');
const path = require('node:path');
for (const [entry, globalName] of [['app',undefined], ['projection','rkProjection'], ['routing','fourPortRouting']]) {
  esbuild.buildSync({entryPoints:[path.join(__dirname,entry+'.ts')],bundle:true,format:'iife',globalName,platform:'browser',target:'es2022',outfile:path.join(__dirname,'../assets',entry === 'app' ? 'viewer.js' : entry+'.js')});
  if(entry !== 'app') esbuild.buildSync({entryPoints:[path.join(__dirname,entry+'.ts')],bundle:true,format:'cjs',platform:'node',target:'es2022',outfile:path.join(__dirname,'../assets',entry+'.cjs')});
}
