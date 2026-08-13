// @ts-check
import { defineConfig } from 'astro/config';

import starlight from '@astrojs/starlight';

// https://astro.build/config
export default defineConfig({
  // Set this to the real deployed domain once one exists (Vercel assigns one on first
  // deploy, or point a custom domain at it). Needed for canonical URLs and the sitemap.
  // site: 'https://your-domain-here',
  integrations: [
    starlight({
      title: 'OpenLead',
      description:
        'A fully local roadmap, Kanban board, and agent memory for AI coding agents.',
      favicon: '/favicon.svg',
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/Ege-BULUT/openlead' },
      ],
      customCss: ['./src/styles/openlead-theme.css'],
      editLink: {
        baseUrl: 'https://github.com/Ege-BULUT/openlead/edit/main/docs/',
      },
      sidebar: [
        {
          label: 'Start here',
          items: [
            { label: 'Overview', slug: 'docs' },
            { label: 'Quick start', slug: 'docs/quick-start' },
            { label: 'The golden rule', slug: 'docs/golden-rule' },
          ],
        },
        {
          label: 'CLI reference',
          items: [
            { label: 'project_cli.py', slug: 'docs/cli/project' },
            { label: 'roadmap_cli.py', slug: 'docs/cli/roadmap' },
            { label: 'tasks_cli.py', slug: 'docs/cli/tasks' },
            { label: 'memory_cli.py', slug: 'docs/cli/memory' },
          ],
        },
        {
          label: 'Using OpenLead',
          items: [
            { label: 'With an AI coding agent', slug: 'docs/agents' },
            { label: 'Architecture', slug: 'docs/architecture' },
          ],
        },
        {
          label: 'More',
          items: [{ label: 'FAQ / what this is not', slug: 'docs/faq' }],
        },
      ],
    }),
  ],
});
