# openlead-site

The OpenLead marketing site and documentation, an Astro project meant to deploy on Vercel.
The landing page lives at `src/pages/index.astro`; the docs are Starlight-powered content
under `src/content/docs/docs/` (served at `/docs/*`).

## Structure

```
src/
├── assets/screenshots/     product screenshots, reused on the landing page
├── content/docs/docs/      the actual doc pages (Starlight content collection)
├── pages/index.astro       the custom landing page (outside Starlight)
└── styles/openlead-theme.css   reskins Starlight's default palette to match
                                the product's own templates/*.html design tokens
```

## Commands

| Command | Action |
|---|---|
| `npm install` | Install dependencies |
| `npm run dev` | Local dev server at `localhost:4321` |
| `npm run build` | Build to `./dist/` |
| `npm run preview` | Preview the production build locally |

## Deploying

This is a stock Astro + Starlight project; Vercel detects it with zero configuration. Set
`site` in `astro.config.mjs` to the real deployed domain once one exists, needed for
canonical URLs and the sitemap.
