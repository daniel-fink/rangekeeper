// Plotly write_html post_script. Read a same-origin host's theme when embedded;
// otherwise follow the OS preference. Update layout only, preserving drill-down,
// zoom, legend selections, object colours and all numerical data.
(() => {
  const plot = document.getElementById('{plot_id}');
  const modes = __RK_MODES__;
  const originalTitle = plot.layout.title?.text || '';
  const originalTop = plot._fullLayout.margin.t;
  const originalHeight = plot._fullLayout.height;
  const partition = plot.data.every(trace => ['sunburst', 'treemap'].includes(trace.type));
  const preference = window.matchMedia('(prefers-color-scheme: dark)');
  // Plotly uses a fixed pale fill for active menu items. Keep controls legible
  // in both host themes, including their open and hover states.
  const controls = document.createElement('style');
  controls.textContent = `
    .updatemenu-item-rect { fill: var(--rk-menu-background) !important; }
    .updatemenu-header:hover .updatemenu-item-rect,
    .updatemenu-dropdown-button:hover .updatemenu-item-rect {
      fill: var(--rk-menu-hover) !important;
    }
    .updatemenu-container text { fill: var(--rk-menu-text) !important; }
  `;
  document.head.appendChild(controls);
  let host = window;
  try {
    if (window.parent !== window && window.parent.document.body) host = window.parent;
  } catch (_) { /* Cross-origin notebooks use the OS fallback. */ }

  function mode() {
    const root = host.document.documentElement;
    const body = host.document.body;
    if (body.hasAttribute('data-jp-theme-light')) {
      return body.getAttribute('data-jp-theme-light') === 'false' ? 'dark' : 'light';
    }
    // The docs site (Zensical) names its scheme on the body.
    if (body.hasAttribute('data-md-color-scheme')) {
      return body.getAttribute('data-md-color-scheme') === 'slate' ? 'dark' : 'light';
    }
    const declared = root.getAttribute('data-theme') || root.getAttribute('data-bs-theme');
    if (declared === 'dark' || declared === 'light') return declared;
    if (root.classList.contains('dark')) return 'dark';
    if (root.classList.contains('light') || host.document.querySelector('article.content')) return 'light';
    return preference.matches ? 'dark' : 'light';
  }

  let lastStyle;
  function update() {
    const colors = modes[mode()];
    const article = host.document.querySelector('article.content');
    const content = article || host.document.querySelector('.jp-RenderedHTMLCommon')
      || host.document.querySelector('.md-typeset') || host.document.body;
    const hostStyle = host.getComputedStyle(content);
    const background = host.getComputedStyle(host.document.body).backgroundColor;
    const embedded = host !== window;
    const paper = embedded && background !== 'rgba(0, 0, 0, 0)' && background !== 'transparent'
      ? background : colors.background;
    const font = embedded ? hostStyle.fontFamily : __RK_FONT__;
    const text = embedded ? hostStyle.color : colors.text;
    const width = plot.clientWidth;
    const key = JSON.stringify([paper, text, font, colors.grid, width]);
    if (key === lastStyle) return;
    lastStyle = key;
    document.body.style.margin = '0';
    document.body.style.backgroundColor = paper;
    document.documentElement.style.colorScheme = mode();
    document.documentElement.style.setProperty('--rk-menu-background', paper);
    document.documentElement.style.setProperty('--rk-menu-hover', colors.grid);
    document.documentElement.style.setProperty('--rk-menu-text', text);
    const layout = {
      width,
      paper_bgcolor: paper, plot_bgcolor: paper,
      'font.color': text, 'font.family': font,
      'hoverlabel.bgcolor': paper, 'hoverlabel.bordercolor': colors.grid,
      'hoverlabel.font.color': text, 'hoverlabel.font.family': font,
      'modebar.bgcolor': paper, 'modebar.color': text,
    };
    // Keep the title readable at narrow book widths without reducing font size.
    // Existing HTML titles retain their authored formatting.
    if (originalTitle && !originalTitle.includes('<')) {
      const limit = Math.max(18, Math.floor((width - 65) / 9));
      const lines = [''];
      for (const word of originalTitle.split(/\s+/)) {
        const last = lines.length - 1;
        if (lines[last] && lines[last].length + word.length + 1 > limit) lines.push(word);
        else lines[last] += (lines[last] ? ' ' : '') + word;
      }
      layout['title.text'] = lines.join('<br>');
      layout['margin.t'] = originalTop + 24 * (lines.length - 1);
    }
    if (partition) {
      layout.height = Math.min(originalHeight, width + (layout['margin.t'] || originalTop) + 20);
      try {
        if (window.frameElement) window.frameElement.style.height = (layout.height + 20) + 'px';
      } catch (_) { /* Fixed-height cross-origin embeds remain scrollable. */ }
    }
    for (const axis of Object.keys(plot.layout).filter(key => /^[xy]axis\d*$/.test(key))) {
      layout[axis + '.gridcolor'] = colors.grid;
      layout[axis + '.linecolor'] = colors.grid;
      layout[axis + '.zerolinecolor'] = colors.grid;
      layout[axis + '.color'] = text;
    }
    for (let index = 0; index < (plot.layout.updatemenus || []).length; index++) {
      const menu = 'updatemenus[' + index + ']';
      layout[menu + '.bgcolor'] = paper;
      layout[menu + '.bordercolor'] = colors.grid;
      layout[menu + '.font.color'] = text;
      layout[menu + '.font.family'] = font;
    }
    Plotly.relayout(plot, layout);
  }

  const observer = new MutationObserver(update);
  for (const element of [host.document.documentElement, host.document.body]) {
    observer.observe(element, {
      attributes: true,
      attributeFilter: [
        'class', 'data-theme', 'data-bs-theme', 'data-jp-theme-light', 'data-md-color-scheme',
      ],
    });
  }
  preference.addEventListener('change', update);
  const resize = new ResizeObserver(update);
  resize.observe(plot);
  window.addEventListener('pagehide', () => {
    observer.disconnect();
    resize.disconnect();
    preference.removeEventListener('change', update);
  }, {once: true});
  update();
})();
