#!/usr/bin/env node
const crypto = require('crypto');
const sharp = require('sharp');
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
    const images = [];
    const warnings = [];
    const rendered = await renderMathMarkdown(text, { cache, images, warnings });
    process.stdout.write(JSON.stringify({ markdown: rendered, images, warnings }));
  } catch (err) {
    process.stderr.write(String((err && err.stack) || err));
    process.exitCode = 1;
  }
});

async function renderMathMarkdown(text, context) {
  let out = '';
  let i = 0;
  while (i < text.length) {
    if (text.startsWith('$$', i)) {
      const end = findClosing(text, i + 2, '$$');
      if (end !== -1) {
        const expr = text.slice(i + 2, end);
        out += await buildImageTag(expr, true, context);
        i = end + 2;
        continue;
      }
    }
    if (text.startsWith('\\[', i)) {
      const end = findClosing(text, i + 2, '\\]');
      if (end !== -1) {
        const expr = text.slice(i + 2, end);
        out += await buildImageTag(expr, true, context);
        i = end + 2;
        continue;
      }
    }
    if (text.startsWith('\\(', i)) {
      const end = findClosing(text, i + 2, '\\)');
      if (end !== -1) {
        const expr = text.slice(i + 2, end);
        out += await buildImageTag(expr, false, context);
        i = end + 2;
        continue;
      }
    }
    if (text[i] === '$' && text[i + 1] !== '$') {
      const end = findInlineDollarEnd(text, i + 1);
      if (end !== -1) {
        const expr = text.slice(i + 1, end);
        out += await buildImageTag(expr, false, context);
        i = end + 1;
        continue;
      }
    }
    out += text[i];
    i += 1;
  }
  return out;
}

async function buildImageTag(expr, displayMode, context) {
  const normalized = expr.trim();
  if (!normalized) {
    return displayMode ? '\n' : '';
  }

  const key = `${displayMode ? 'display' : 'inline'}:${normalized}`;
  let image = context.cache.get(key);
  if (!image) {
    try {
      image = await renderExpressionPng(normalized, displayMode);
      context.cache.set(key, image);
      context.images.push({
        cid: image.cid,
        filename: image.filename,
        mime_type: 'image/png',
        data_base64: image.dataBase64,
      });
    } catch (err) {
      context.warnings.push(`Failed to render math expression as PNG: ${normalized.slice(0, 120)} (${String(err.message || err)})`);
      return displayMode ? `\n$$${normalized}$$\n` : `$${normalized}$`;
    }
  }

  const alt = displayMode ? 'displayed equation' : 'equation';
  const sizeAttrs = image.width && image.height
    ? ` width="${image.width}" height="${image.height}"`
    : '';

  if (displayMode) {
    return `\n<div style="margin:12px 0; text-align:center;"><img src="cid:${image.cid}" alt="${alt}"${sizeAttrs} style="display:block; margin:0 auto; max-width:100%; height:auto;" /></div>\n`;
  }
  return `<img src="cid:${image.cid}" alt="${alt}"${sizeAttrs} style="display:inline-block; vertical-align:middle; max-width:100%; height:auto;" />`;
}

async function renderExpressionPng(expr, displayMode) {
  const svg = await texsvg(expr);
  const density = displayMode ? 288 : 240;
  const image = sharp(Buffer.from(svg, 'utf8'), { density });
  const pngBuffer = await image.png().toBuffer();
  const metadata = await sharp(pngBuffer).metadata();
  const hash = crypto.createHash('sha1').update(`${displayMode ? 'd' : 'i'}:${expr}`).digest('hex').slice(0, 16);

  return {
    cid: `math-${hash}`,
    filename: `math-${hash}.png`,
    dataBase64: pngBuffer.toString('base64'),
    width: metadata.width || undefined,
    height: metadata.height || undefined,
  };
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
