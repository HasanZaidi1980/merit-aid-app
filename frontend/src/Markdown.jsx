// Minimal, dependency-free Markdown renderer for the AI answer panel.
//
// Claude replies in Markdown, but the panel used to render the raw string, so
// answers showed literal "**" and "-" characters. This handles the small subset
// a mission-statement answer actually uses: headings, bullet and numbered
// lists, bold, italic and inline code.
//
// SECURITY: escapeHtml() runs FIRST on every piece of input, so any HTML in the
// model output or in an IPEDS mission statement is inert text by the time the
// formatting regexes add tags. The only markup reaching dangerouslySetInnerHTML
// is what this file generates.

const escapeHtml = (s) => s
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

function inline(text) {
  let t = escapeHtml(text);
  t = t.replace(/`([^`]+)`/g, '<code>$1</code>');
  t = t.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');   // bold first...
  t = t.replace(/\*([^*]+)\*/g, '<em>$1</em>');               // ...then italic
  t = t.replace(/(^|[\s(])_([^_]+)_(?=[\s.,;:!?)]|$)/g, '$1<em>$2</em>');
  return t;
}

function toHtml(src) {
  const out = [];
  // Blank lines separate blocks; a list runs until the first non-list line.
  const blocks = String(src || '').replace(/\r\n/g, '\n').split(/\n{2,}/);

  for (const block of blocks) {
    const lines = block.split('\n').filter((l) => l.trim() !== '');
    if (!lines.length) continue;

    const bullet = lines.every((l) => /^\s*[-*+]\s+/.test(l));
    const number = lines.every((l) => /^\s*\d+[.)]\s+/.test(l));

    if (bullet) {
      out.push('<ul>' + lines
        .map((l) => `<li>${inline(l.replace(/^\s*[-*+]\s+/, ''))}</li>`)
        .join('') + '</ul>');
    } else if (number) {
      out.push('<ol>' + lines
        .map((l) => `<li>${inline(l.replace(/^\s*\d+[.)]\s+/, ''))}</li>`)
        .join('') + '</ol>');
    } else if (/^#{1,6}\s/.test(lines[0])) {
      const level = Math.min(lines[0].match(/^#+/)[0].length + 2, 6);
      out.push(`<h${level}>${inline(lines[0].replace(/^#+\s*/, ''))}</h${level}>`);
      if (lines.length > 1) out.push(`<p>${lines.slice(1).map(inline).join('<br/>')}</p>`);
    } else {
      out.push(`<p>${lines.map(inline).join('<br/>')}</p>`);
    }
  }
  return out.join('');
}

export default function Markdown({ text, className }) {
  return (
    <div className={className} dangerouslySetInnerHTML={{ __html: toHtml(text) }} />
  );
}
