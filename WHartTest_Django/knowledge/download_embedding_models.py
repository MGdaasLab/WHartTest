#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BGE-M3 嵌入模型下载脚本
下载 BGE-M3 模型到本地缓存
"""
import os
from pathlib import Path

# BGE-M3 模型信息
MODEL_NAME = 'BAAI/bge-m3'
MODEL_SIZE = '4.2GB'

def setup_cache_directory():
    """设置缓存目录"""
    # 基于当前文件位置，定位到项目根目录
    project_root = Path(__file__).resolve().parent.parent
    cache_dir = project_root / '.cache' / 'huggingface'
    cache_dir.mkdir(parents=True, exist_ok=True)
    print(f"📦 缓存位置: {cache_dir}")
    return cache_dir

def check_model_exists(cache_dir):
    """检查BGE-M3模型是否已存在"""
    model_path = cache_dir / f"models--{MODEL_NAME.replace('/', '--')}"
    return model_path.exists() and any(model_path.iterdir())

def download_bge_m3():
    """下载BGE-M3模型"""
    cache_dir = setup_cache_directory()
    
    if check_model_exists(cache_dir):
        print(f"✅ BGE-M3模型已存在，跳过下载")
        print(f"📁 缓存位置: {cache_dir}")
        return True
    
    try:
        print(f"🚀 开始下载BGE-M3模型: {MODEL_NAME}")
        print(f"💡 提示: 模型大小约{MODEL_SIZE}，请耐心等待...")
        print(f"🖥️  使用设备: cpu")
        print(f"📦 正在下载模型文件...")
        
        # 设置缓存目录
        os.environ['HF_HUB_CACHE'] = str(cache_dir)
        
        # 动态导入以确保使用正确的缓存路径
        from sentence_transformers import SentenceTransformer
        
        # 下载模型
        model = SentenceTransformer(MODEL_NAME)
        
        print(f"✅ BGE-M3模型下载成功!")
        print(f"📁 缓存位置: {cache_dir}")
        return True
        
    except Exception as e:
        print(f"❌ 模型下载失败: {str(e)}")
        print(f"💡 请检查网络连接和存储空间")
        return False

if __name__ == '__main__':
    print("BGE-M3 嵌入模型下载器")
    print("=" * 30)
    download_bge_m3()
