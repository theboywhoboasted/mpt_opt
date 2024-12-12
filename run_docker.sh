#!/usr/bin/env bash

if [ "$1" == "--dev" ]; then
    tag="dev"
else
    tag="prod"
fi

# Build image
docker build --tag=webapp/mpt:$tag -f Dockerfile.$tag . 

# List docker images
docker image ls

# mkdir cache
mkdir -p $(pwd)/__cache__

# Run flask app
docker run -v $(pwd)/__cache__:/app/cache -p 127.0.0.1:8080:8080 webapp/mpt:$tag