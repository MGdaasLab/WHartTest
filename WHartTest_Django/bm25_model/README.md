---
license: apache-2.0
language:
- en
pipeline_tag: sentence-similarity
---
Repository with files to perform BM25 searches with [FastEmbed](https://github.com/qdrant/fastembed).

[BM25 (Best Matching 25)](https://en.wikipedia.org/wiki/Okapi_BM25) is a ranking function used by search engines to estimate the relevance of documents to a given search query.

### Usage

> Note:
This model is supposed to be used with Qdrant. Vectors have to be configured with [Modifier.IDF](https://qdrant.tech/documentation/concepts/indexing/?q=modifier#idf-modifier).

Here's an example of BM25 with [FastEmbed](https://github.com/qdrant/fastembed).

```py
from fastembed import SparseTextEmbedding

documents = [
    "You should stay, study and sprint.",
    "History can only prepare us to be surprised yet again.",
]

model = SparseTextEmbedding(model_name="Qdrant/bm25")
embeddings = list(model.embed(documents))

# [
#     SparseEmbedding(
#         values=array([1.67419738, 1.67419738, 1.67419738, 1.67419738]),
#         indices=array([171321964, 1881538586, 150760872, 1932363795])),
#     SparseEmbedding(values=array(
#         [1.66973021, 1.66973021, 1.66973021, 1.66973021, 1.66973021]),
#                     indices=array([
#                         578407224, 1849833631, 1008800696, 2090661150,
#                         1117393019
#                     ]))
# ]
```



```