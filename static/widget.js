(function () {
  'use strict';

  const API_BASE = '__BASE_URL__';

  const CSS = [
    // Themes
    '.fbw-light{--fbw-bg:#f0f2f5;--fbw-card:#fff;--fbw-border:#e4e6eb;--fbw-text:#1c1e21;--fbw-sub:#65676b;--fbw-btn:#e4e6eb;--fbw-btn-text:#050505;--fbw-accent:#1877f2;}',
    '.fbw-dark{--fbw-bg:#18191a;--fbw-card:#242526;--fbw-border:#3a3b3c;--fbw-text:#e4e6eb;--fbw-sub:#b0b3b8;--fbw-btn:#3a3b3c;--fbw-btn-text:#e4e6eb;--fbw-accent:#4599ff;}',
    // Wrapper — fills available host width; container query anchor for inner elements
    '.fbw-wrap{width:100%;background:var(--fbw-bg);border-radius:12px;padding:12px;box-sizing:border-box;font-family:system-ui,-apple-system,sans-serif;font-size:14px;line-height:1.5;container-type:inline-size;}',
    // Header
    '.fbw-header{display:flex;align-items:center;gap:10px;padding:0 0 12px;}',
    '.fbw-avatar{width:44px;height:44px;border-radius:50%;object-fit:cover;background:var(--fbw-border);flex-shrink:0;}',
    '.fbw-avatar-ph{width:44px;height:44px;border-radius:50%;background:var(--fbw-accent);display:flex;align-items:center;justify-content:center;color:#fff;font-weight:900;font-size:20px;font-family:Georgia,serif;flex-shrink:0;}',
    '.fbw-page-name{font-weight:700;font-size:15px;color:var(--fbw-text);}',
    '.fbw-follow-btn{margin-left:auto;padding:6px 14px;border-radius:6px;border:none;background:var(--fbw-accent);color:#fff;font-size:13px;font-weight:600;cursor:pointer;text-decoration:none;display:inline-block;white-space:nowrap;}',
    // Card grid — mobile: single column; gap replaces per-card margins
    '.fbw-grid{display:grid;grid-template-columns:1fr;gap:16px;align-items:start;}',
    // Cards
    '.fbw-card{background:var(--fbw-card);border-radius:10px;border:1px solid var(--fbw-border);overflow:hidden;}',
    '.fbw-card-header{display:flex;align-items:center;gap:8px;padding:12px 12px 6px;}',
    '.fbw-card-avatar{width:36px;height:36px;border-radius:50%;object-fit:cover;background:var(--fbw-border);flex-shrink:0;}',
    '.fbw-card-avatar-ph{width:36px;height:36px;border-radius:50%;background:var(--fbw-accent);display:flex;align-items:center;justify-content:center;color:#fff;font-weight:900;font-size:15px;font-family:Georgia,serif;flex-shrink:0;}',
    '.fbw-card-meta{display:flex;flex-direction:column;}',
    '.fbw-card-name{font-weight:600;font-size:13px;color:var(--fbw-text);}',
    '.fbw-card-time{font-size:12px;color:var(--fbw-sub);}',
    '.fbw-card-body{padding:6px 12px 10px;}',
    '.fbw-card-text{color:var(--fbw-text);white-space:pre-wrap;word-break:break-word;}',
    '.fbw-card-text-clamped{display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden;}',
    '.fbw-expand-btn{background:none;border:none;color:var(--fbw-accent);cursor:pointer;padding:4px 0 0;font-size:13px;font-family:inherit;}',
    '.fbw-card-img{width:100%;display:block;max-height:400px;object-fit:cover;}',
    '.fbw-card-footer{padding:8px 12px;}',
    '.fbw-view-btn{display:inline-block;padding:6px 14px;border-radius:6px;background:var(--fbw-btn);color:var(--fbw-btn-text);text-decoration:none;font-size:13px;font-weight:600;}',
    // States
    '.fbw-loading{display:flex;align-items:center;justify-content:center;padding:40px;}',
    '@keyframes fbw-spin{to{transform:rotate(360deg)}}',
    '.fbw-spinner{width:30px;height:30px;border:3px solid var(--fbw-border);border-top-color:var(--fbw-accent);border-radius:50%;animation:fbw-spin 0.8s linear infinite;}',
    '.fbw-error{padding:16px;color:var(--fbw-sub);text-align:center;}',
    '.fbw-empty{padding:24px;color:var(--fbw-sub);text-align:center;}',
    // Tablet ≥ 600px: 2-column grid
    '@container (min-width:600px){.fbw-grid{grid-template-columns:1fr 1fr;}}',
    // Desktop ≥ 1024px: 3-column grid
    '@container (min-width:1024px){.fbw-grid{grid-template-columns:1fr 1fr 1fr;}.fbw-avatar{width:52px;height:52px;}.fbw-avatar-ph{width:52px;height:52px;font-size:22px;}.fbw-page-name{font-size:16px;}}',
  ].join('');

  function injectStyles() {
    if (document.getElementById('fbw-styles')) return;
    const styleEl = document.createElement('style');
    styleEl.id = 'fbw-styles';
    styleEl.textContent = CSS;
    document.head.appendChild(styleEl);
  }

  // Minimal DOM builder: buildElement('div', { className: 'foo' }, child1, child2)
  function buildElement(tag, props, ...children) {
    const node = Object.assign(document.createElement(tag), props);
    for (const child of children) {
      if (child != null) node.append(child);
    }
    return node;
  }

  function relativeTime(timestamp) {
    const elapsedSeconds = Math.floor((Date.now() - new Date(timestamp)) / 1000);
    const ago = (count, unit) => count + ' ' + unit + (count > 1 ? 's' : '') + ' ago';
    if (elapsedSeconds < 60) return 'just now';
    if (elapsedSeconds < 3600) return ago(Math.floor(elapsedSeconds / 60), 'minute');
    if (elapsedSeconds < 86400) return ago(Math.floor(elapsedSeconds / 3600), 'hour');
    if (elapsedSeconds < 604800) return ago(Math.floor(elapsedSeconds / 86400), 'day');
    return ago(Math.floor(elapsedSeconds / 604800), 'week');
  }

  function renderLoading(container) {
    container.replaceChildren(
      buildElement('div', { className: 'fbw-loading' }, buildElement('div', { className: 'fbw-spinner' }))
    );
  }

  function renderError(container, message) {
    container.replaceChildren(
      buildElement('div', { className: 'fbw-error', textContent: '\u26a0 ' + message })
    );
  }

  function buildAvatar(pictureUrl, size) {
    if (pictureUrl) {
      return buildElement('img', {
        className: size === 'large' ? 'fbw-avatar' : 'fbw-card-avatar',
        src: pictureUrl,
        alt: '',
        loading: 'lazy',
      });
    }
    return buildElement('div', {
      className: size === 'large' ? 'fbw-avatar-ph' : 'fbw-card-avatar-ph',
      textContent: 'f',
    });
  }

  function buildWidgetHeader(page) {
    const followButton = buildElement('a', {
      className: 'fbw-follow-btn',
      href: 'https://facebook.com/' + encodeURIComponent(page.id),
      target: '_blank',
      rel: 'noopener noreferrer',
      textContent: 'Follow',
    });

    return buildElement('div', { className: 'fbw-header' },
      buildAvatar(page.picture_url, 'large'),
      buildElement('div', { className: 'fbw-page-name', textContent: page.name }),
      followButton,
    );
  }

  function initExpandButton(textEl, btn) {
    if (textEl.scrollHeight > textEl.clientHeight + 2) {
      btn.style.display = 'block';
      btn.textContent = 'See more';
      let expanded = false;
      btn.onclick = function () {
        expanded = !expanded;
        textEl.classList.toggle('fbw-card-text-clamped', !expanded);
        btn.textContent = expanded ? 'See less' : 'See more';
      };
    }
  }

  function buildCardHeader(post, page) {
    return buildElement('div', { className: 'fbw-card-header' },
      buildAvatar(page.picture_url, 'small'),
      buildElement('div', { className: 'fbw-card-meta' },
        buildElement('div', { className: 'fbw-card-name', textContent: page.name }),
        buildElement('div', { className: 'fbw-card-time', textContent: relativeTime(post.created_time) }),
      ),
    );
  }

  function buildCardBody(post) {
    const textEl = buildElement('div', {
      className: 'fbw-card-text fbw-card-text-clamped',
      textContent: post.message,
    });
    const expandBtn = buildElement('button', {
      className: 'fbw-expand-btn',
      style: 'display:none',
    });
    setTimeout(() => initExpandButton(textEl, expandBtn), 0);
    return buildElement('div', { className: 'fbw-card-body' }, textEl, expandBtn);
  }

  function buildCardImage(post) {
    return buildElement('img', {
      className: 'fbw-card-img',
      src: post.full_picture,
      alt: '',
      loading: 'lazy',
    });
  }

  function buildCardFooter(post) {
    return buildElement('div', { className: 'fbw-card-footer' },
      buildElement('a', {
        className: 'fbw-view-btn',
        href: post.permalink_url,
        target: '_blank',
        rel: 'noopener noreferrer',
        textContent: 'View on Facebook',
      }),
    );
  }

  function buildCard(post, page) {
    const card = buildElement('div', { className: 'fbw-card' }, buildCardHeader(post, page));
    if (post.message) card.appendChild(buildCardBody(post));
    if (post.full_picture) card.appendChild(buildCardImage(post));
    if (post.permalink_url) card.appendChild(buildCardFooter(post));
    return card;
  }

  // Single in-flight promise shared across all widgets on the page.
  let fetchPromise = null;

  function fetchPosts(limit) {
    if (!fetchPromise) {
      fetchPromise = fetch(API_BASE + '/api/posts?limit=' + limit)
        .then(async function (response) { return { response, data: await response.json() }; });
    }
    return fetchPromise;
  }

  async function renderWidget(container) {
    const limit = Math.min(20, Math.max(1, parseInt(container.dataset.limit || '5', 10)));
    const theme = container.dataset.theme === 'dark' ? 'dark' : 'light';

    container.className = 'fbw-wrap fbw-' + theme;
    renderLoading(container);

    let postsResponse;
    try {
      postsResponse = await fetchPosts(limit);
    } catch (err) {
      console.error(err);
      renderError(container, 'Could not load posts.');
      return;
    }
    const { response, data } = postsResponse;

    if (!response.ok) {
      renderError(container, data.error || 'Error ' + response.status);
      return;
    }

    container.replaceChildren(buildWidgetHeader(data.page));

    if (!data.posts?.length) {
      container.appendChild(buildElement('div', { className: 'fbw-empty', textContent: 'No posts found.' }));
      return;
    }

    const grid = buildElement('div', { className: 'fbw-grid' });
    for (const post of data.posts) {
      grid.appendChild(buildCard(post, data.page));
    }
    container.appendChild(grid);
  }

  function initWidgets() {
    injectStyles();
    document.querySelectorAll('.fb-widget').forEach(renderWidget);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initWidgets);
  } else {
    initWidgets();
  }

})();
