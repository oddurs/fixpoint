---
paths:
  - "site/**"
---

# The project page

- `csr = false` and `prerender = true` (`site/src/routes/+layout.js`): no client
  JavaScript, ever. Interaction is CSS.
- The post's body is `site/src/post.md`, rendered by `site/src/routes/+page.server.js`
  (nasm listings, TeX quotes, the inlined figure). The lead, tagline and commands are in
  `+page.svelte`.
- Style: a 2003 personal page by someone who owns the TeXbook. Latin Modern, ragged right,
  hyphenated, blue underlined links, booktabs tables, lowercase voice. Polish rough edges;
  don't modernise it.
- Colours are tokens on `:root` in `site/src/app.css`. Indent with tabs.
- Served at the root of fixpoint.oddurs.com: no base path. Links to assets are absolute.
- Monospace never takes the body's negative word-spacing; inline code never wraps.
- Check changes at 1280 and 390 px wide; nothing may scroll sideways except code blocks.
