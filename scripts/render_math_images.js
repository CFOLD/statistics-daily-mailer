#!/usr/bin/env node
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const katex = require('katex');
const { chromium } = require('playwright');

const KATEX_CSS_PATH = require.resolve('katex/dist/katex.min.css');
const KATEX_DIST_DIR = path.dirname(KATEX_CSS_PATH);
const KATEX_FONTS_DIR = path.join(KATEX_DIST_DIR, 'fonts');

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => {
  input += chunk;
});
process.stdin.on('end', async () => {
  let browser;
  try {
    const payload = JSON.parse(input || '{}');
    const text = String(payload.text || '');
    const mode = payload.mode === 'preview' ? 'preview' : 'email';
    const css = loadKatexCss();
    browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({ viewport: { width: 1200, height: 800 }, deviceScaleFactor: 2 });
    const cache = new Map();
    const images = [];
    const rendered = await renderMathMarkdown(text, mode, page, css, cache, images);
    process.stdout.write(JSON.stringify({ markdown: rendered, images }));
  } catch (err) {
    process.stderr.write(String((err && err.stack) || err));
    process.exitCode = 1;
  } finally {
    if (browser) {
      await browser.close().catch(() => {});
    }
  }
});

function loadKatexCss() {
  const css = fs.readFileSync(KATEX_CSS_PATH, 'utf8');
  return css.replace(/url\(fonts\/([^\)]+)\)/g, (_, fontFile) => {
    const clean = String(fontFile).replace(/^['"]|['"]$/g, '');
    const absolute = path.join(KATEX_FONTS_DIR, clean).replace(/\\/g, '/');
    return `url("file://${absolute}")`;
  });
}

async function renderMathMarkdown(text, mode, page, css, cache, images) {
  let out = '';
  let i = 0;
  while (i < text.length) {
    if (text.startsWith('$$', i)) {
      const end = findClosing(text, i + 2, '$$');
      if (end !== -1) {
        const expr = text.slice(i + 2, end);
        out += await buildImageTag(expr, true, mode, page, css, cache, images);
        i = end + 2;
        continue;
      }
    }
    if (text.startsWith('\\[', i)) {
      const end = findClosing(text, i + 2, '\\]');
      if (end !== -1) {
        const expr = text.slice(i + 2, end);
        out += await buildImageTag(expr, true, mode, page, css, cache, images);
        i = end + 2;
        continue;
      }
    }
    if (text.startsWith('\\(', i)) {
      const end = findClosing(text, i + 2, '\\)');
      if (end !== -1) {
        const expr = text.slice(i + 2, end);
        out += await buildImageTag(expr, false, mode, page, css, cache, images);
        i = end + 2;
        continue;
      }
    }
    if (text[i] === '$' && text[i + 1] !== '$') {
      const end = findInlineDollarEnd(text, i + 1);
      if (end !== -1) {
        const expr = text.slice(i + 1, end);
        out += await buildImageTag(expr, false, mode, page, css, cache, images);
        i = end + 1;
        continue;
      }
    }
    out += text[i];
    i += 1;
  }
  return out;
}

async function buildImageTag(expr, displayMode, mode, page, css, cache, images) {
  const normalized = expr.trim();
  if (!normalized) {
    return displayMode ? '\n' : '';
  }
  const key = `${displayMode ? 'display' : 'inline'}:${normalized}`;
  let image = cache.get(key);
  if (!image) {
    image = await renderExpressionImage(normalized, displayMode, mode, page, css);
    cache.set(key, image);
    if (mode === 'email') {
      images.push({ cid: image.cid, mimeType: 'image/png', data: image.data });
    }
  }
  const src = mode === 'preview' ? image.dataUri : `cid:${image.cid}`;
  const alt = escapeHtml(normalized);
  if (displayMode) {
    return `\n<div style="margin:12px 0; text-align:center;"><img src="${src}" alt="${alt}" style="display:block; margin:0 auto; max-width:100%; height:auto;" /></div>\n`;
  }
  return `<img src="${src}" alt="${alt}" style="display:inline-block; vertical-align:middle; height:auto; max-width:100%;" />`;
}

async function renderExpressionImage(expr, displayMode, mode, page, css) {
  const html = katex.renderToString(expr, {
    throwOnError: false,
    output: 'html',
    displayMode,
    strict: 'ignore',
    trust: false,
  });
  const wrapperStyle = displayMode
    ? 'display:inline-block; padding:10px 14px; background:#ffffff; color:#111827;'
    : 'display:inline-block; padding:4px 6px; background:#ffffff; color:#111827;';

  await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>${css}
    body { margin:0; padding:0; background:transparent; }
    #math-root { ${wrapperStyle} }
  </style></head><body><div id="math-root">${html}</div></body></html>`);

  const locator = page.locator('#math-root');
  const buffer = await locator.screenshot({ type: 'png', omitBackground: true });
  const base64 = buffer.toString('base64');
  const cid = `math-${crypto.createHash('sha1').update(keyForCid(expr, displayMode)).digest('hex')}@openclaw`;
  return {
    cid,
    data: base64,
    dataUri: `data:image/png;base64,${base64}`,
  };
}

function keyForCid(expr, displayMode) {
  return `${displayMode ? 'display' : 'inline'}:${expr}`;
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
