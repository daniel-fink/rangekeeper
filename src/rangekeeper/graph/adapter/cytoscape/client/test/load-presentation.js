const { buildSync } = require("esbuild");
const Module = require("node:module"),
  path = require("node:path");
const filename = path.join(__dirname, "../presentation.ts");
const code = buildSync({
  entryPoints: [filename],
  bundle: true,
  platform: "node",
  format: "cjs",
  write: false,
}).outputFiles[0].text;
const m = new Module(filename, module);
m._compile(code, filename);
module.exports = m.exports;
