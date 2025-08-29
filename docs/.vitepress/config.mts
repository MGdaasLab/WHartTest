import { defineConfig } from 'vitepress'

// https://vitepress.dev/reference/site-config
export default defineConfig({
  title: "WHartTest",
  description: "WHartTest 是一个基于 Django REST Framework 构建的AI驱动测试自动化平台，核心功能是通过AI智能生成测试用例。平台集成了 LangChain、MCP（Model Context Protocol）工具调用、项目管理、需求评审、测试用例管理以及先进的知识库管理和文档理解功能。利用大语言模型和HuggingFace嵌入模型的能力，自动化生成高质量的测试用例，并结合知识库提供更精准的测试辅助，为测试团队提供一个完整的智能测试管理解决方案.",
  lastUpdated: true,
  cleanUrls: true,
  head: [
    ['meta', { name: 'keywords', content: 'WHartTest, 测试自动化, AI 测试, 知识库, LangChain, LangGraph, MCP, Django, Vue, VitePress' }],
    ['meta', { property: 'og:title', content: 'WHartTest 文档' }],
    ['meta', { name: 'keywords', content: 'WHartTest, 测试自动化, AI 测试, 知识库, LangChain, LangGraph, MCP, Django, Vue, VitePress' }],
    ['meta', { property: 'og:title', content: 'WHartTest 文档' }],
    ['meta', { property: 'og:description', content: 'AI驱动的智能测试自动化平台，集成知识库、LangChain、MCP 工具与项目/用例/需求管理' }],
    ['style', {}, `
      :root {
        --vp-c-brand-1: #3370ff;
        --vp-c-brand-2: #4c7fff;
        --vp-c-brand-3: #2b63e6;
        --vp-button-brand-bg: linear-gradient(135deg, #3370ff 0%, #4c7fff 100%);
        --vp-button-brand-hover-bg: linear-gradient(135deg, #2b63e6 0%, #3370ff 100%);
        --vp-button-brand-text: #ffffff;
      }
      
      .VPButton.brand {
        background: linear-gradient(135deg, #3370ff 0%, #4c7fff 100%) !important;
        border: 1px solid #3370ff !important;
        color: white !important;
      }
      
      .VPButton.brand:hover {
        background: linear-gradient(135deg, #2b63e6 0%, #3370ff 100%) !important;
        border: 1px solid #2b63e6 !important;
      }
    `]
  ],
  themeConfig: {
    // https://vitepress.dev/reference/default-theme-config
    
    nav: [
      { text: '首页', link: '/' },
      { text: '项目介绍', link: '/project-introduction' },
      { text: '未来规划', link: '/future-planning' },
      { text: '快速上手', link: '/quick-start/django-deployment' },
      { text: 'API文档', link: '/api/knowledge-api' },
      { text: '开发指南', link: '/developer-guide/contributing' }
    ],

    sidebar: {
      '/quick-start/': [
        {
          text: '快速上手',
          items: [
            { text: '后端部署 (Django)', link: '/quick-start/django-deployment' },
            { text: '前端部署 (Vue)', link: '/quick-start/vue-deployment' },
            { text: 'MCP 工具部署', link: '/quick-start/mcp-deployment' }
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
        },
        {
          text: '组件依赖',
          items: [
            { text: '前端', link: '/core-concepts/frontend-dependencies' },
            { text: '后端', link: '/core-concepts/backend-dependencies' }
          ]
        }
      ]
    },

    // 如需展示仓库链接，请在此处配置你们的仓库地址
    // socialLinks: [
    //   { icon: 'github', link: 'https://github.com/your-org/your-repo' }
    // ]
  }
})
