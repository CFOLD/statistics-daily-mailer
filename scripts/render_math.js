#!/usr/bin/env node
const katex = require('katex');

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => {
  input += chunk;
});
process.stdin.on('end', () => {
  try {
    const payload = JSON.parse(input || '{}');
    const text = String(payload.text || '');
    const rendered = renderMath(text);
    process.stdout.write(JSON.stringify({ html: rendered }));
  } catch (err) {
    process.stderr.write(String(err && err.stack || err));
    process.exit(1);
  }
});

function renderMath(text) {
  let out = '';
  let i = 0;
  while (i < text.length) {
    if (text.startsWith('$$', i)) {
      const end = findClosing(text, i + 2, '$$');
      if (end !== -1) {
        const expr = text.slice(i + 2, end);
        out += renderExpr(expr, true);
        i = end + 2;
        continue;
      }
    }
    if (text.startsWith('\\[', i)) {
      const end = findClosing(text, i + 2, '\\]');
      if (end !== -1) {
        const expr = text.slice(i + 2, end);
        out += renderExpr(expr, true);
        i = end + 2;
        continue;
      }
    }
    if (text.startsWith('\\(', i)) {
      const end = findClosing(text, i + 2, '\\)');
      if (end !== -1) {
        const expr = text.slice(i + 2, end);
        out += renderExpr(expr, false);
        i = end + 2;
        continue;
      }
    }
    if (text[i] === '$' && text[i + 1] !== '$') {
      const end = findInlineDollarEnd(text, i + 1);
      if (end !== -1) {
        const expr = text.slice(i + 1, end);
        out += renderExpr(expr, false);
        i = end + 1;
        continue;
      }
    }
    out += text[i];
    i += 1;
  }
  return out;
}

function renderExpr(expr, displayMode) {
  try {
    return katex.renderToString(expr.trim(), {
      throwOnError: false,
      output: 'html',
      displayMode,
      strict: 'ignore',
      trust: false,
    });
  } catch {
    return displayMode ? `$$${expr}$$` : `$${expr}$`;
  }
}

function findClosing(text, start, token) {
  let i = start;
  while (i < text.length) {
    if (text.startsWith(token, i) && text[i - 1] !== '\\') {
      return i;
    }
    i += 1;
  }
  return -1;
}

function findInlineDollarEnd(text, start) {
  let i = start;
  while (i < text.length) {
    if (text[i] === '$' && text[i - 1] !== '\\') {
      return i;
    }
    if (text[i] === '\n') {
      return -1;
    }
    i += 1;
  }
  return -1;
}
