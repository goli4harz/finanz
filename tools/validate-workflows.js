#!/usr/bin/env node
// Statischer Validator für alle n8n-Workflow-JSON-Dateien im Repo-Root.
// Keine npm-Abhaengigkeit (nur Node-Bordmittel fs/path) - laueft mit `node tools/validate-workflows.js`.
//
// Prueft genau die Bugklassen, die in diesem Repo wiederholt real aufgetreten sind
// (siehe docs/REPARATURPLAN.md P0.1-P0.4, P2.12):
//   1. JSON-Validitaet
//   2. Doppelte Node-IDs innerhalb eines Workflows
//   3. Haengende Connections (Quelle/Ziel referenziert einen nicht existierenden Node-Namen)
//   4. JS-Syntaxfehler in allen jsCode-Nodes (inkl. top-level await, wie n8n es tatsaechlich ausfuehrt)
//   5. Merge-Nodes im riskanten combineAll-Modus (Kreuzprodukt-Risiko, siehe P0.3)
//   6. "//"-JS-Kommentare, die versehentlich in ein SQL-Template durchgesickert sind (siehe P0.1)
//   7. Mehrere unverbundene Endnodes in einem als Sub-Workflow aufrufbaren Workflow (siehe P0.4)
//
// Exit-Code 0 = keine Fehler, 1 = mindestens ein Fehler gefunden. Warnungen (combineAll,
// mehrere Endnodes) beeinflussen den Exit-Code NICHT - sie sind bewusste Architekturentscheidungen
// wert, kein automatischer Fehlschlag.

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');

function findWorkflowFiles(dir) {
  return fs.readdirSync(dir)
    .filter(f => f.toLowerCase().endsWith('.json'))
    .filter(f => {
      // n8n-Workflow-Exporte haben immer "nodes" + "connections" auf oberster Ebene -
      // schliesst z.B. package.json-artige Dateien im Root aus, falls je vorhanden.
      try {
        const d = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
        return Array.isArray(d.nodes) && typeof d.connections === 'object';
      } catch (e) {
        return true; // ungueltiges JSON soll trotzdem als Fund auftauchen, nicht stillschweigend uebersprungen werden
      }
    })
    .sort();
}

function checkJsSyntax(code) {
  // n8n fuehrt Code-Node-Inhalt als Body einer async-Funktion aus (deshalb ist top-level
  // await erlaubt) - eine nackte `new Function(code)` lehnt das faelschlich ab, siehe
  // Node.js-Verhalten beim Bau dieses Tools selbst beobachtet.
  new Function('return (async () => {\n' + code + '\n})');
}

function findDuplicateNodeIds(nodes) {
  const seen = new Map();
  const dupes = new Set();
  for (const n of nodes) {
    if (seen.has(n.id)) dupes.add(n.id);
    seen.set(n.id, true);
  }
  return [...dupes];
}

function findDanglingConnections(nodes, connections) {
  const names = new Set(nodes.map(n => n.name));
  const problems = [];
  for (const [src, out] of Object.entries(connections)) {
    if (!names.has(src)) problems.push('Quelle nicht gefunden: "' + src + '"');
    for (const kind of Object.keys(out)) { // "main", ggf. "ai_tool" etc.
      for (const branch of out[kind] || []) {
        for (const t of branch || []) {
          if (t && t.node && !names.has(t.node)) {
            problems.push('Ziel nicht gefunden: "' + src + '" -> "' + t.node + '"');
          }
        }
      }
    }
  }
  return problems;
}

function findCombineAllMerges(nodes) {
  return nodes
    .filter(n => n.type === 'n8n-nodes-base.merge' && n.parameters && n.parameters.mode === 'combineAll')
    .map(n => n.name);
}

function findLeakedJsCommentsInSql(nodes) {
  const findings = [];
  const sqlKeyword = /\b(SELECT|INSERT|UPDATE|DELETE|WITH)\b/i;

  function scanForLeakedComment(text, label) {
    // "//" ist in echtem SQL nie gueltig (kein Ganzzeilen-Kommentarstil ausser "--") -
    // einzige legitime Ausnahme: literal "http://"/"https://" innerhalb eines String-Literals.
    const idx = text.indexOf('//');
    if (idx === -1) return;
    const before = text.slice(Math.max(0, idx - 8), idx);
    if (/https?:$/i.test(before)) return;
    findings.push(label);
  }

  for (const n of nodes) {
    const query = n.parameters && n.parameters.query;
    if (typeof query === 'string' && sqlKeyword.test(query)) {
      scanForLeakedComment(query, n.name + ' (query-Parameter)');
    }
    const code = n.parameters && n.parameters.jsCode;
    if (typeof code === 'string') {
      // Nur Inhalte innerhalb von Template-Literalen pruefen, die wie SQL aussehen -
      // vermeidet Fehlalarme durch normale Kommentare im umgebenden JS-Code.
      const templateLiteralRe = /`([^`]*)`/g;
      let m;
      while ((m = templateLiteralRe.exec(code)) !== null) {
        const literal = m[1];
        if (sqlKeyword.test(literal)) {
          scanForLeakedComment(literal, n.name + ' (SQL-Template-Literal)');
        }
      }
    }
  }
  return findings;
}

function findMultipleEndNodes(nodes, connections) {
  const sourceNames = new Set(Object.keys(connections));
  const nonStructural = new Set(['n8n-nodes-base.stickyNote']);
  const endNodes = nodes
    .filter(n => !nonStructural.has(n.type))
    .filter(n => !sourceNames.has(n.name))
    .map(n => n.name);
  return endNodes;
}

function validateFile(file) {
  const filePath = path.join(ROOT, file);
  const result = { file, errors: [], warnings: [] };

  let raw;
  try {
    raw = fs.readFileSync(filePath, 'utf8');
  } catch (e) {
    result.errors.push('Datei nicht lesbar: ' + e.message);
    return result;
  }

  let d;
  try {
    d = JSON.parse(raw);
  } catch (e) {
    result.errors.push('Ungueltiges JSON: ' + e.message);
    return result;
  }

  const nodes = Array.isArray(d.nodes) ? d.nodes : [];
  const connections = (d.connections && typeof d.connections === 'object') ? d.connections : {};

  const dupeIds = findDuplicateNodeIds(nodes);
  if (dupeIds.length > 0) {
    result.errors.push('Doppelte Node-IDs: ' + dupeIds.join(', '));
  }

  const dangling = findDanglingConnections(nodes, connections);
  for (const p of dangling) result.errors.push('Haengende Connection: ' + p);

  for (const n of nodes) {
    const code = n.parameters && n.parameters.jsCode;
    if (typeof code === 'string' && code.trim() !== '') {
      try {
        checkJsSyntax(code);
      } catch (e) {
        result.errors.push('JS-Syntaxfehler in "' + n.name + '": ' + e.message);
      }
    }
  }

  const combineAll = findCombineAllMerges(nodes);
  for (const name of combineAll) {
    result.warnings.push('Merge-Node im combineAll-Modus (Kreuzprodukt-Risiko pruefen): "' + name + '"');
  }

  const leaked = findLeakedJsCommentsInSql(nodes);
  for (const f of leaked) {
    result.errors.push('Moeglicher "//"-Kommentar im SQL-Text: ' + f);
  }

  const endNodes = findMultipleEndNodes(nodes, connections);
  if (endNodes.length > 1) {
    result.warnings.push(
      'Mehrere unverbundene Endnodes (' + endNodes.length + '): ' + endNodes.join(', ')
    );
  }

  return result;
}

function main() {
  const files = findWorkflowFiles(ROOT);
  let errorCount = 0;
  let warningCount = 0;

  console.log('Validiere ' + files.length + ' Workflow-Dateien in ' + ROOT + '\n');

  for (const file of files) {
    const result = validateFile(file);
    if (result.errors.length === 0 && result.warnings.length === 0) continue;

    console.log('# ' + file);
    for (const e of result.errors) {
      console.log('  FEHLER: ' + e);
      errorCount++;
    }
    for (const w of result.warnings) {
      console.log('  WARNUNG: ' + w);
      warningCount++;
    }
    console.log('');
  }

  console.log('---');
  console.log(files.length + ' Dateien geprueft, ' + errorCount + ' Fehler, ' + warningCount + ' Warnungen.');
  process.exit(errorCount > 0 ? 1 : 0);
}

main();
