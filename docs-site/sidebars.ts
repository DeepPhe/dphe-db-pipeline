import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  pipelineGuide: [
    'index',
    {
      type: 'category',
      label: 'Getting Started',
      collapsed: false,
      items: ['getting-started/quickstart'],
    },
    {
      type: 'category',
      label: 'Pipeline Stages',
      collapsed: false,
      items: [
        'loader/README',
        'importer/source-modes',
        'importer/architecture',
      ],
    },
    {
      type: 'category',
      label: 'Loader',
      collapsed: true,
      items: ['loader/API_REFERENCE', 'loader/EXTRACT_100_PATIENTS'],
    },
    {
      type: 'category',
      label: 'OMOP Importer',
      collapsed: true,
      items: [
        'importer/config-reference',
        'importer/table-catalog',
        'importer/troubleshooting',
      ],
    },
    {
      type: 'category',
      label: 'Architecture Decisions',
      collapsed: true,
      items: [
        'importer/adrs/sqlite-is-the-only-destination',
        'importer/adrs/mysql-is-a-read-only-source',
        'importer/adrs/json-mode-writes-directly-to-calculated-tables',
      ],
    },
    'distribution',
  ],
};

export default sidebars;
