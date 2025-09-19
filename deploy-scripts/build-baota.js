#!/usr/bin/env node

// 面板构建脚本
// 使用相对路径，适配部署环境

process.env.DEPLOY_TYPE = 'baota';

const { execSync } = require('child_process');

console.log('🏗️  开始构建面板版本...');
console.log('📁 base路径: ./ (相对路径)');

try {
  // 执行VitePress构建
  execSync('vitepress build docs', { stdio: 'inherit' });
  console.log('✅ 面板版本构建完成！');
  console.log('📂 构建输出目录: docs/.vitepress/dist');
  console.log('💡 提示: 请将 docs/.vitepress/dist 目录上传到面板');
} catch (error) {
  console.error('❌ 构建失败:', error.message);
  process.exit(1);
}