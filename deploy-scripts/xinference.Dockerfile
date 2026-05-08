ARG XINFERENCE_BASE_IMAGE=xprobe/xinference:latest-cpu
FROM ${XINFERENCE_BASE_IMAGE}

# The base image currently ships peft 0.17.1 with transformers 5.6.2.
# That combination breaks sentence-transformers imports when launching
# bge-m3 / bge-reranker-v2-m3 in Xinference.
RUN python -m pip install --no-cache-dir --upgrade "peft==0.19.1"
