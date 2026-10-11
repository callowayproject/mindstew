import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'mindstew',
  description: 'mindstew documentation',
  // GitHub Pages serves project sites under /<repo>/
  base: '/mindstew/',
  // ponytail: docs/ also holds agent notes and research; exclude them from the site
  srcExclude: ['agents/**', 'research/**'],
  themeConfig: {
    nav: [
      { text: 'Guide', link: '/getting-started' },
      { text: 'Reference', link: '/reference/cli' },
      { text: 'Contributing', link: '/design-decisions/review-system-design' },
    ],
    // ponytail: hand-listed sidebar, add new pages here
    sidebar: [
      {
        text: 'Guide',
        items: [
          { text: 'Getting started', link: '/getting-started' },
          { text: 'Tutorial', link: '/tutorial' },
          { text: 'Concepts', link: '/concepts' },
        ],
      },
      {
        text: 'How-to',
        items: [
          { text: 'Ingesting sources', link: '/how-to/ingest-sources' },
          { text: 'Configuring providers', link: '/how-to/configure-providers' },
        ],
      },
      {
        text: 'Reference',
        items: [{ text: 'CLI', link: '/reference/cli' }],
      },
      {
        text: 'Contributing',
        collapsed: true,
        items: [
          { text: 'Agent skills UX', link: '/design-decisions/agent-skills-ux-design' },
          { text: 'Graph color mode', link: '/design-decisions/graph-color-mode-design' },
          { text: 'MCP server tool surface', link: '/design-decisions/mcp-server-tool-surface-design' },
          { text: 'Project export/import', link: '/design-decisions/project-export-import-design' },
          { text: 'Read sources only', link: '/design-decisions/read-sources-only-design' },
          { text: 'Review system', link: '/design-decisions/review-system-design' },
          { text: 'Settings / model routing', link: '/design-decisions/settings-model-routing-design' },
          { text: 'Structural lint', link: '/design-decisions/structural-lint-design' },
          { text: 'Vertical-slice plan', link: '/design-decisions/vertical-slice-plan-design' },
          { text: 'ADR: Image captioning pipeline', link: '/adr/image-captioning-pipeline-design' },
        ],
      },
    ],
    socialLinks: [{ icon: 'github', link: 'https://github.com/callowayproject/mindstew' }],
  },
})
