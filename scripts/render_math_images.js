#!/usr/bin/env node
const texsvg = require('texsvg');

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => {
  input += chunk;
});
process.stdin.on('end', async () => {
  try {
    const payload = JSON.parse(input || '{}');
    const text = String(payload.text || '');
    const cache = new Map();
    const rendered = await renderMathMarkdown(text, cache);
    process.stdout.write(JSON.stringify({ markdown: rendered }));
  } catch (err) {
    process.stderr.write(String((err && err.stack) || err));
    process.exitCode = 1;
  }
});

async function renderMathMarkdown(text, cache) {
  let out = '';
  let i = 0;
  while (i < text.length) {
    if (text.startsWith('$$', i)) {
      const end = findClosing(text, i + 2, '$$');
      if (end !== -1) {
        const expr = text.slice(i + 2, end);
        out += await buildImageTag(expr, true, cache);
        i = end + 2;
        continue;
      }
    }
    if (text.startsWith('\\[', i)) {
      const end = findClosing(text, i + 2, '\\]');
      if (end !== -1) {
        const expr = text.slice(i + 2, end);
        out += await buildImageTag(expr, true, cache);
        i = end + 2;
        continue;
      }
    }
    if (text.startsWith('\\(', i)) {
      const end = findClosing(text, i + 2, '\\)');
      if (end !== -1) {
        const expr = text.slice(i + 2, end);
        out += await buildImageTag(expr, false, cache);
        i = end + 2;
        continue;
      }
    }
    if (text[i] === '$' && text[i + 1] !== '$') {
      const end = findInlineDollarEnd(text, i + 1);
      if (end !== -1) {
        const expr = text.slice(i + 1, end);
        out += await buildImageTag(expr, false, cache);
        i = end + 1;
        continue;
      }
    }
    out += text[i];
    i += 1;
  }
  return out;
}

async function buildImageTag(expr, displayMode, cache) {
  const normalized = expr.trim();
  if (!normalized) {
    return displayMode ? '\n' : '';
  }
  const key = `${displayMode ? 'display' : 'inline'}:${normalized}`;
  let dataUri = cache.get(key);
  if (!dataUri) {
    dataUri = await renderExpressionSvgDataUri(normalized);
    cache.set(key, dataUri);
  }
  const alt = escapeHtml(normalized);
  if (displayMode) {
    return `\n<div style="margin:12px 0; text-align:center;"><img src="${dataUri}" alt="${alt}" style="display:block; margin:0 auto; max-width:100%; height:auto;" /></div>\n`;
  }
  return `<img src="${dataUri}" alt="${alt}" style="display:inline-block; vertical-align:middle; height:auto; max-width:100%;" />`;
}

async function renderExpressionSvgDataUri(expr) {
  const svg = await texsvg(expr);
  return `data:image/svg+xml;base64,${Buffer.from(svg, 'utf8').toString('base64')}`;
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

function escapeHtml(value) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
