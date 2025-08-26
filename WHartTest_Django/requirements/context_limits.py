"""
模型上下文限制配置和检测
"""

import tiktoken
import logging

logger = logging.getLogger(__name__)

# 主流模型的上下文限制（token数）
MODEL_CONTEXT_LIMITS = {
    # OpenAI GPT 系列
    'gpt-3.5-turbo': 4096,
    'gpt-3.5-turbo-16k': 16384,
    'gpt-4': 8192,
    'gpt-4-32k': 32768,
    'gpt-4-turbo': 128000,
    'gpt-4o': 128000,
    'gpt-4o-mini': 128000,
    
    # Claude 系列
    'claude-3-haiku': 200000,
    'claude-3-sonnet': 200000,
    'claude-3-opus': 200000,
    'claude-3.5-sonnet': 200000,
    
    # 其他模型
    'gemini-pro': 32768,
    'gemini-1.5-pro': 1000000,
    
    # 本地模型（Ollama等）
    'llama2': 4096,
    'llama3': 8192,
    'qwen': 8192,
    'chatglm': 8192,
    
    # 默认值
    'default': 4096
}

# 预留token数（用于系统提示词、响应等）
RESERVED_TOKENS = 1000

class ContextLimitChecker:
    """上下文限制检测器"""
    
    def __init__(self):
        self.encoders = {}
    
    def get_encoder(self, model_name: str):
        """获取对应模型的编码器"""
        if model_name not in self.encoders:
            try:
                # 尝试获取模型特定的编码器
                if model_name.startswith('gpt'):
                    self.encoders[model_name] = tiktoken.encoding_for_model(model_name)
                else:
                    # 对于其他模型，使用通用编码器
                    self.encoders[model_name] = tiktoken.get_encoding("cl100k_base")
            except Exception as e:
                logger.warning(f"无法获取模型 {model_name} 的编码器，使用默认编码器: {e}")
                self.encoders[model_name] = tiktoken.get_encoding("cl100k_base")
        
        return self.encoders[model_name]
    
    def count_tokens(self, text: str, model_name: str = 'gpt-3.5-turbo') -> int:
        """计算文本的token数量"""
        try:
            encoder = self.get_encoder(model_name)
            return len(encoder.encode(text))
        except Exception as e:
            logger.error(f"计算token数量失败: {e}")
            # 粗略估算：中文约1.5字符/token，英文约4字符/token
            # 取平均值2.5字符/token
            return len(text) // 2.5
    
    def get_context_limit(self, model_name: str) -> int:
        """获取模型的上下文限制"""
        # 尝试精确匹配
        if model_name in MODEL_CONTEXT_LIMITS:
            return MODEL_CONTEXT_LIMITS[model_name]
        
        # 尝试模糊匹配
        for model_key, limit in MODEL_CONTEXT_LIMITS.items():
            if model_key in model_name.lower():
                return limit
        
        # 返回默认值
        logger.warning(f"未知模型 {model_name}，使用默认上下文限制")
        return MODEL_CONTEXT_LIMITS['default']
    
    def check_context_limit(self, text: str, model_name: str = 'gpt-3.5-turbo') -> dict:
        """检查文本是否超过模型上下文限制"""
        token_count = self.count_tokens(text, model_name)
        context_limit = self.get_context_limit(model_name)
        available_tokens = context_limit - RESERVED_TOKENS
        
        result = {
            'model_name': model_name,
            'token_count': token_count,
            'context_limit': context_limit,
            'available_tokens': available_tokens,
            'reserved_tokens': RESERVED_TOKENS,
            'exceeds_limit': token_count > available_tokens,
            'usage_percentage': (token_count / available_tokens) * 100,
            'remaining_tokens': available_tokens - token_count
        }
        
        # 添加建议
        if result['exceeds_limit']:
            result['suggestion'] = 'SPLIT_REQUIRED'
            result['message'] = f"文本超出上下文限制，需要拆分。当前{token_count}tokens，限制{available_tokens}tokens"
        elif result['usage_percentage'] > 80:
            result['suggestion'] = 'SPLIT_RECOMMENDED'
            result['message'] = f"文本接近上下文限制，建议拆分。使用率{result['usage_percentage']:.1f}%"
        else:
            result['suggestion'] = 'OK'
            result['message'] = f"文本大小合适，使用率{result['usage_percentage']:.1f}%"
        
        return result
    
    def calculate_optimal_chunk_size(self, total_text: str, model_name: str = 'gpt-3.5-turbo') -> dict:
        """计算最优的分块大小"""
        total_tokens = self.count_tokens(total_text, model_name)
        available_tokens = self.get_context_limit(model_name) - RESERVED_TOKENS
        
        if total_tokens <= available_tokens:
            return {
                'needs_splitting': False,
                'total_tokens': total_tokens,
                'available_tokens': available_tokens,
                'message': '文档无需拆分'
            }
        
        # 计算需要的分块数
        chunks_needed = (total_tokens // available_tokens) + 1
        optimal_chunk_tokens = total_tokens // chunks_needed
        
        # 转换为字符数（粗略估算）
        optimal_chunk_chars = optimal_chunk_tokens * 2.5
        
        return {
            'needs_splitting': True,
            'total_tokens': total_tokens,
            'available_tokens': available_tokens,
            'chunks_needed': chunks_needed,
            'optimal_chunk_tokens': optimal_chunk_tokens,
            'optimal_chunk_chars': int(optimal_chunk_chars),
            'message': f'建议拆分为{chunks_needed}个分块，每个分块约{optimal_chunk_tokens}tokens'
        }

# 全局实例
context_checker = ContextLimitChecker()

def check_document_context_limit(content: str, model_name: str = None) -> dict:
    """检查文档是否超过上下文限制的便捷函数"""
    if not model_name:
        # 从配置中获取默认模型
        from django.conf import settings
        model_name = getattr(settings, 'DEFAULT_LLM_MODEL', 'gpt-3.5-turbo')
    
    return context_checker.check_context_limit(content, model_name)

def get_optimal_split_size(content: str, model_name: str = None) -> int:
    """获取最优拆分大小的便捷函数"""
    if not model_name:
        from django.conf import settings
        model_name = getattr(settings, 'DEFAULT_LLM_MODEL', 'gpt-3.5-turbo')
    
    result = context_checker.calculate_optimal_chunk_size(content, model_name)
    return result.get('optimal_chunk_chars', 2000)
