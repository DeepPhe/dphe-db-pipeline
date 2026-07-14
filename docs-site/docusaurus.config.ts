import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';
import type {EditUrlFunction} from '@docusaurus/plugin-content-docs';

const organizationName = 'DeepPhe';
const projectName = 'dphe-db-pipeline';
const repositoryUrl = `https://github.com/${organizationName}/${projectName}`;
const editUrl: EditUrlFunction = ({docPath}) =>
  `${repositoryUrl}/edit/main/docs/${docPath}`;

const config: Config = {
  title: 'DeepPhe DB Pipeline Docs',
  tagline: 'Load DeepPhe NLP output, build OMOP SQLite data, and extract patient summaries',
  url: 'https://deepphe.github.io',
  baseUrl: '/dphe-db-pipeline/',
  trailingSlash: false,

  organizationName,
  projectName,
  onBrokenLinks: 'throw',

  future: {
    v4: true,
  },

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
    mdx1Compat: {
      comments: true,
      admonitions: true,
    },
  },

  presets: [
    [
      'classic',
      {
        docs: {
          path: '../docs',
          routeBasePath: '/',
          sidebarPath: './sidebars.ts',
          editUrl,
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    colorMode: {
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'DeepPhe DB Pipeline',
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'pipelineGuide',
          position: 'left',
          label: 'Pipeline Guide',
        },
        {
          href: repositoryUrl,
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'DeepPhe',
          items: [
            {
              label: 'Pipeline repository',
              href: repositoryUrl,
            },
            {
              label: 'Quickstart',
              to: '/getting-started/quickstart',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} DeepPhe.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
