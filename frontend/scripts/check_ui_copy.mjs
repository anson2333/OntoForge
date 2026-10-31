/** Guard application copy and protocol values without touching backend data. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../renderer');
const messages = JSON.parse(fs.readFileSync(path.join(root, 'locales/ui.json'), 'utf8'));
const allowedText = new Set(['OntoForge', 'demo / demo1234', 'v', 'A-Z', 'Ollama', 'KB']);
const allowedAttribute = /^(OntoForge|[\w.-]+\.(?:pdf|json|yaml)|https?:\/\/.*|[\w.-]+:[\w.-]+|\d.*|0\.\d.*)$/;
const failures = [];
function files(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap(e => e.isDirectory() ? files(path.join(dir, e.name)) : /\.tsx$/.test(e.name) ? [path.join(dir, e.name)] : []);
}
for (const file of files(root).filter(f => !f.endsWith('i18n.tsx'))) {
  const source = fs.readFileSync(file, 'utf8');
  const tree = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const report = (node, text) => failures.push(`${path.relative(root, file)}:${tree.getLineAndCharacterOfPosition(node.getStart(tree)).line + 1}: ${text}`);
  function visit(node) {
    if (ts.isJsxText(node)) {
      const value = node.text.trim().replace(/\s+/g, ' ');
      if (/[A-Za-z]{2}|[\u4e00-\u9fff]/.test(value) && !allowedText.has(value)) report(node, `Untranslated JSX text: ${value}`);
    }
    if (ts.isJsxAttribute(node) && node.initializer) {
      const name = node.name.getText(tree);
      if (/^(title|placeholder|aria-label|alt|label)$/.test(name) && ts.isStringLiteral(node.initializer)) {
        const value = node.initializer.text;
        if (/[A-Za-z]{2}/.test(value) && !allowedAttribute.test(value)) report(node, `Untranslated ${name}: ${value}`);
      }
      if (/^(value|key|className|id|type|data-)/.test(name) && /\b(?:t|uiLabel)\(/.test(node.initializer.getText(tree))) {
        report(node, `Translated protocol/style attribute: ${name}`);
      }
    }
    if (ts.isCallExpression(node) && node.expression.getText(tree) === 't' && ts.isStringLiteral(node.arguments[0])) {
      if (!messages[node.arguments[0].text]) report(node, `Missing catalog entry: ${node.arguments[0].text}`);
    }
    ts.forEachChild(node, visit);
  }
  visit(tree);
}
for (const [key, pair] of Object.entries(messages)) {
  assert.equal(pair.length, 2, key);
  const placeholders = text => [...text.matchAll(/\{(\w+)\}/g)].map(m => m[1]).sort();
  assert.deepEqual(placeholders(pair[0]), placeholders(pair[1]), key);
}
assert.deepEqual(failures, [], failures.join('\n'));
console.log(`PASS: static UI copy, ${Object.keys(messages).length} translation entries, placeholders, and untranslated protocol values.`);
