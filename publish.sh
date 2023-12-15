#!/bin/bash

BASE=mlo
USER=mlo # Change this to your GASPAR
TAG=v1   # Change this to the version you want to publish

REGISTRY=ic-registry.epfl.ch
# REGISTRY=docker.io

docker build . -t ${BASE}/${USER}:${TAG} --network=host &&
    docker tag ${BASE}/${USER}:${TAG} ${REGISTRY}/${BASE}/${USER}:${TAG} &&
    docker push ${REGISTRY}/${BASE}/${USER}:${TAG}
