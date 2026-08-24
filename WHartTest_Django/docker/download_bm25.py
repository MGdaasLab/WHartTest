import os
import traceback

from fastembed import SparseTextEmbedding

os.environ['FASTEMBED_CACHE_PATH'] = '/root/.cache/fastembed'
endpoints = [os.environ.get('HF_ENDPOINT'), 'https://hf-mirror.com', 'https://huggingface.co']
success = False

for ep in endpoints:
    if not ep:
        continue
    print(f'Trying to download model using HF_ENDPOINT: {ep}')
    os.environ['HF_ENDPOINT'] = ep
    try:
        SparseTextEmbedding('Qdrant/bm25')
        success = True
        print(f'Successfully downloaded BM25 model using endpoint: {ep}')
        break
    except Exception as e:
        traceback.print_exc()
        print(f'Failed download with endpoint {ep}: {e}')

if not success:
    raise RuntimeError('Failed to download BM25 model from all endpoints')
