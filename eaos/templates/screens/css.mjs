// EAOS design-drift stats: @projectwallace/css-analyzer over a built site's CSS.
//
// Run by eaos/screens/audit.py as a separate process:  node css.mjs <config.json>
// The config names the analyzer's module folder and the CSS to read ({files: [...], inline: [...]}).
// The result is one JSON object on stdout: the analyzer's own counts, unchanged, for the keys EAOS reads.
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const config = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const require = createRequire(join(config.modules.css, 'eaos-resolve.js'));
const { analyze } = await import(pathToFileURL(require.resolve('@projectwallace/css-analyzer')).href);

const css = [...config.files.map((file) => readFileSync(file, 'utf8')), ...(config.inline || [])].join('\n');
const result = analyze(css);
const count = (block) => ({ total: block.total, unique: block.totalUnique, values: block.unique });
const specificity = result.selectors.specificity;
process.stdout.write(JSON.stringify({
  lines_of_code: result.stylesheet.sourceLinesOfCode,
  rules: result.rules.total,
  selectors: result.selectors.total,
  declarations: result.declarations.total,
  colors: count(result.values.colors),
  font_sizes: count(result.values.fontSizes),
  font_families: count(result.values.fontFamilies),
  line_heights: count(result.values.lineHeights),
  border_radiuses: count(result.values.borderRadiuses),
  box_shadows: count(result.values.boxShadows),
  z_indexes: count(result.values.zindexes),
  custom_properties: result.properties.custom.total,
  important: result.declarations.importants ? result.declarations.importants.total : null,
  specificity: { max: specificity.max, mean: specificity.mean, unique: specificity.totalUnique },
  units: count(result.values.units),
}) + '\n');
