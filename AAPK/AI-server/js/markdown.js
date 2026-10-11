const escapeHtml = value => String(value ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

function renderMarkdown(source) {
  let text = String(source ?? '').replace(/\r\n/g,'\n');
  const blocks = [];
  text = text.replace(/```([\w+-]*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    const id = blocks.length;
    blocks.push(`<pre class="code-block"><div class="code-header"><span>${escapeHtml(lang || 'code')}</span><button class="copy-code" data-code-index="${id}" type="button">Copy</button></div><code>${escapeHtml(code.replace(/\n$/,''))}</code></pre>`);
    return `@@CODE${id}@@`;
  });
  text = escapeHtml(text);
  text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  text = text.replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
  text = text.replace(/`([^`\n]+)`/g, '<code class="inline-code">$1</code>');
  text = text.replace(/^###### (.+)$/gm,'<h6>$1</h6>').replace(/^##### (.+)$/gm,'<h5>$1</h5>').replace(/^#### (.+)$/gm,'<h4>$1</h4>').replace(/^### (.+)$/gm,'<h3>$1</h3>').replace(/^## (.+)$/gm,'<h2>$1</h2>').replace(/^# (.+)$/gm,'<h1>$1</h1>');
  text = text.replace(/^[-*] (.+)$/gm,'<li>$1</li>').replace(/(<li>.*<\/li>\n?)+/g, m => `<ul>${m}</ul>`);
  text = text.replace(/^\d+\. (.+)$/gm,'<li>$1</li>').replace(/(<li>.*<\/li>\n?)+/g, m => m.includes('<ul>') ? m : `<ol>${m}</ol>`);
  text = text.replace(/^> (.+)$/gm,'<blockquote>$1</blockquote>');
  text = text.replace(/\*\*([^*\n]+)\*\*/g,'<strong>$1</strong>').replace(/__([^_\n]+)__/g,'<strong>$1</strong>');
  text = text.replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g,'<em>$1</em>').replace(/(?<!_)_([^_\n]+)_(?!_)/g,'<em>$1</em>');
  text = text.replace(/\n\n+/g,'</p><p>').replace(/\n/g,'<br>');
  text = `<p>${text}</p>`.replace(/<p>\s*(<h[1-6]|<pre|<ul|<ol|<blockquote)/g,'$1').replace(/(<\/h[1-6]>|<\/pre>|<\/ul>|<\/ol>|<\/blockquote>)\s*<\/p>/g,'$1');
  blocks.forEach((html, i) => { text = text.replace(`@@CODE${i}@@`, html); });
  return text;
}

function bindCopyCode(container) {
  container.querySelectorAll('.copy-code').forEach(button => {
    button.onclick = async () => {
      const code = button.closest('.code-block')?.querySelector('code')?.innerText || '';
      try { await navigator.clipboard.writeText(code); button.innerText='Copied'; setTimeout(()=>button.innerText='Copy',1200); }
      catch { button.innerText='Copy failed'; setTimeout(()=>button.innerText='Copy',1200); }
    };
  });
}
