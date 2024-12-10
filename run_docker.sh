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

# Run flask app
docker run -v $(pwd)/cache:/app/cache -p 127.0.0.1:8081:8081 webapp/mpt:$tag