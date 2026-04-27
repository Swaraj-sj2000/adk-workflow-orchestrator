/**
 * Lightweight markdown renderer for AI-generated text.
 * Handles: headings, bold, italic, bullet lists, numbered lists,
 * horizontal rules, and paragraph breaks.
 * No external dependencies required.
 */
import React from 'react';

function parseInline(text) {
  // Process bold+italic, bold, italic with unique placeholder approach
  const parts = [];
  const regex = /\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|\*(.+?)\*|`([^`]+)`/g;
  let last = 0;
  let m;
  let key = 0;
  while ((m = regex.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    if (m[1]) parts.push(<strong key={key++}><em>{m[1]}</em></strong>);
    else if (m[2]) parts.push(<strong key={key++}>{m[2]}</strong>);
    else if (m[3]) parts.push(<em key={key++}>{m[3]}</em>);
    else if (m[4]) parts.push(<code key={key++} style={{background:'var(--surface,#f3f4f6)',padding:'1px 5px',borderRadius:4,fontSize:'0.88em'}}>{m[4]}</code>);
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts.length === 1 && typeof parts[0] === 'string' ? parts[0] : parts;
}

export default function Markdown({ text, className }) {
  if (!text) return null;

  const lines = String(text).split('\n');
  const elements = [];
  let ulBuffer = [];
  let olBuffer = [];
  let key = 0;

  function flushUl() {
    if (!ulBuffer.length) return;
    elements.push(
      <ul key={key++} style={{margin:'6px 0 6px 18px',padding:0,lineHeight:1.6}}>
        {ulBuffer.map((item, i) => (
          <li key={i} style={{marginBottom:2}}>{parseInline(item)}</li>
        ))}
      </ul>
    );
    ulBuffer = [];
  }
  function flushOl() {
    if (!olBuffer.length) return;
    elements.push(
      <ol key={key++} style={{margin:'6px 0 6px 20px',padding:0,lineHeight:1.6}}>
        {olBuffer.map((item, i) => (
          <li key={i} style={{marginBottom:2}}>{parseInline(item)}</li>
        ))}
      </ol>
    );
    olBuffer = [];
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    // Heading
    const h4m = trimmed.match(/^####\s+(.*)/);
    const h3m = trimmed.match(/^###\s+(.*)/);
    const h2m = trimmed.match(/^##\s+(.*)/);
    const h1m = trimmed.match(/^#\s+(.*)/);

    if (h4m || h3m || h2m || h1m) {
      flushUl(); flushOl();
      const lvl = h4m ? 4 : h3m ? 3 : h2m ? 2 : 1;
      const content = (h4m || h3m || h2m || h1m)[1];
      const Tag = `h${Math.min(lvl + 2, 6)}`; // h3-h5 range so they don't dwarf the card
      elements.push(
        <Tag key={key++} style={{margin:'10px 0 4px',fontSize: lvl<=2?'1em':'0.9em', fontWeight:700, color:'var(--text-primary,#1a1a1a)'}}>
          {parseInline(content)}
        </Tag>
      );
      continue;
    }

    // HR
    if (/^[-*_]{3,}$/.test(trimmed)) {
      flushUl(); flushOl();
      elements.push(<hr key={key++} style={{border:'none',borderTop:'1px solid var(--border-soft,#e5e7eb)',margin:'8px 0'}} />);
      continue;
    }

    // Unordered list item  (* or -)
    const ulm = trimmed.match(/^[-*]\s+(.*)/);
    if (ulm) {
      flushOl();
      ulBuffer.push(ulm[1]);
      continue;
    }

    // Ordered list item (1. 2. etc.)
    const olm = trimmed.match(/^\d+\.\s+(.*)/);
    if (olm) {
      flushUl();
      olBuffer.push(olm[1]);
      continue;
    }

    // Empty line — flush buffers, start new paragraph gap
    if (trimmed === '') {
      flushUl(); flushOl();
      // Add a small gap only if we have prior content
      if (elements.length > 0) {
        elements.push(<div key={key++} style={{height:6}} />);
      }
      continue;
    }

    // Plain paragraph line — flush lists, add paragraph
    flushUl(); flushOl();
    elements.push(
      <p key={key++} style={{margin:'3px 0',lineHeight:1.65}}>
        {parseInline(trimmed)}
      </p>
    );
  }

  flushUl(); flushOl();

  return <div className={className} style={{fontSize:'inherit'}}>{elements}</div>;
}
