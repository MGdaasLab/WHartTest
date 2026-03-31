import { defineConfig } from 'vitepress'

// https://vitepress.dev/reference/site-config
export default defineConfig({
  title: "WHartTest",
  description: "WHartTest 是一个基于 Django REST Framework 构建的AI驱动测试自动化平台，核心功能是通过AI智能生成测试用例。平台集成了 LangGraph、MCP（Model Context Protocol）工具调用、项目管理、需求评审、测试用例管理以及先进的知识库管理和文档理解功能。利用大语言模型和HuggingFace嵌入模型的能力，自动化生成高质量的测试用例，并结合知识库提供更精准的测试辅助，为测试团队提供一个完整的智能测试管理解决方案.",
  lastUpdated: true,
  cleanUrls: true,
  ignoreDeadLinks: true,
  base: process.env.DEPLOY_TYPE === 'baota' ? '/docs/' : '/WHartTest/',
  head: [
    ['meta', { name: 'keywords', content: 'WHartTest, 测试自动化, AI 测试, 知识库, LangChain, LangGraph, MCP, Django, Vue, VitePress' }],
    ['meta', { property: 'og:title', content: 'WHartTest 文档' }],
    ['meta', { name: 'keywords', content: 'WHartTest, 测试自动化, AI 测试, 知识库, LangChain, LangGraph, MCP, Django, Vue, VitePress' }],
    ['meta', { property: 'og:title', content: 'WHartTest 文档' }],
    ['meta', { property: 'og:description', content: 'AI驱动的智能测试自动化平台，集成知识库、LangGraph、MCP 工具与项目/用例/需求管理' }],
    ['style', {}, `
      :root {
        --vp-c-brand-1: #00a0e9;
        --vp-c-brand-2: #1aaaeb;
        --vp-c-brand-3: #0090d1;
        --vp-button-brand-bg: linear-gradient(135deg, #00a0e9 0%, #1aaaeb 100%);
        --vp-button-brand-hover-bg: linear-gradient(135deg, #0090d1 0%, #00a0e9 100%);
        --vp-button-brand-text: #ffffff;
      }
      
      .VPButton.brand {
        background: linear-gradient(135deg, #00a0e9 0%, #1aaaeb 100%) !important;
        border: 1px solid #00a0e9 !important;
        color: white !important;
      }
      
      .VPButton.brand:hover {
        background: linear-gradient(135deg, #0090d1 0%, #00a0e9 100%) !important;
        border: 1px solid #0090d1 !important;
      }
    `]
  ],
  themeConfig: {
    // https://vitepress.dev/reference/default-theme-config
    logo: '/img/WHartTest.png',
    
    nav: [
      { text: '首页', link: '/' },
      { text: '项目介绍', link: '/project-introduction' },
      { text: '未来规划', link: '/future-planning' },
      { text: '快速上手', link: '/quick-start/django-deployment' },
      { text: '版本说明', link: '/CHANGELOG' },
      { text: 'API文档', link: '/api/knowledge-api' },
      { text: '开发指南', link: '/developer-guide/contributing' }
    ],

    sidebar: {
      '/quick-start/': [
        {
          text: '快速上手',
          items: [
            { text: 'Docker部署', link: '/quick-start/django-deployment' },
            { text: '本地开发 (Local)',
              items:[
              { text: '前端开发 (Vue)', link: '/quick-start/vue-deployment' },
              { text: '后端开发 (Django)', link: '/quick-start/back-deployment' },
              { text: 'MCP 工具部署 (MCP)', link: '/quick-start/mcp-deployment' },
            ]},
            { text: '快速开始',
                items:[
                    {text: 'UI自动化', link: '/quick-start/uizdh'}]
                },
            { text: '操作手册',
              items:[
                  {text: 'v2.2.0', link: '/quick-start/operation-manual-v2.2'},
              {text: 'v2.1.0', link: '/quick-start/operation-manual-v2.1'},
              { text: 'v2.0.0', link: '/quick-start/operation-manual-v2' },
              { text: 'v1.4.0', link: '/quick-start/operation-manual' },
            ]},
            { text: '常见问题', link: '/quick-start/problem-deployment' }
          ]
        }
      ],
      '/api/': [
        {
          text: 'API 文档',
          items: [
            { text: '知识库 API', link: '/api/knowledge-api' },
            { text: '提示词 API', link: '/api/prompt-api' },
            { text: '需求 API', link: '/api/requirements-api' }
          ]
        }
      ],
      '/developer-guide/': [
        {
          text: '开发指南',
          items: [
            { text: '贡献指南', link: '/developer-guide/contributing' },
            { text: '集成指南', link: '/developer-guide/integration-guide' }
          ]
        }
      ],
      '/': [
        {
          text: '介绍',
          items: [
            { text: '项目介绍', link: '/project-introduction' },
            { text: '未来规划', link: '/future-planning' },
            { text: '许可证', link: '/license' }
          ]
        },
        {
          text: '架构概览',
          items: [
            { text: '前端', link: '/core-concepts/frontend-architecture' },
            { text: '后端', link: '/core-concepts/permission-system' }
          ]
        }
      ]
    },

    // 如需展示仓库链接，请在此处配置你们的仓库地址
    socialLinks: [
      { icon: 'github', link: 'https://github.com/MGdaasLab/WHartTest' }
    ]
  }
})