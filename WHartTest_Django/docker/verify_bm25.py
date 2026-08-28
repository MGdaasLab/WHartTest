import os

os.environ['HF_HUB_OFFLINE'] = '1'

from fastembed import SparseTextEmbedding

SparseTextEmbedding('Qdrant/bm25', specific_model_path='/opt/bm25_model')
print('Successfully loaded BM25 model from local directory')
