FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y \
    cmake \
    g++ \
    gcc

ARG USERNAME=lurawi
ARG USER_UID=1000
ARG USER_GID=${USER_UID}

RUN groupadd --gid ${USER_GID} ${USERNAME} \
    && useradd --uid ${USER_UID} --gid ${USER_GID} -m ${USERNAME} -s /bin/bash

WORKDIR /opt/defaultsite
COPY . /opt/defaultsite

RUN pip install -r requirements.txt

RUN chown -R $USERNAME:${USERNAME} /opt/defaultsite
RUN chmod 755 /opt/defaultsite

USER lurawi

ENV HOST=0.0.0.0
EXPOSE 8081
EXPOSE 3031

ENV TIKTOKEN_CACHE_DIR='/opt/defaultsite/assets'

ENTRYPOINT ["bin/lurawi", "run"]
