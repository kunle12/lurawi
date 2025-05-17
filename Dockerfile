FROM python:3.12.10-slim-bookworm

WORKDIR /opt/defaultsite

COPY . /opt/defaultsite

RUN pip install -r requirements.txt

ENV HOST=0.0.0.0
EXPOSE 8081
EXPOSE 3031

ENV TIKTOKEN_CACHE_DIR='/opt/defaultsite/assets'

ENTRYPOINT ["bin/lurawi", "run"]
