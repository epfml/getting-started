#!/usr/bin/env bash
set -euo pipefail


REGISTRY="${REGISTRY:-ic-registry.epfl.ch}"
IMAGE_PATH="${IMAGE_PATH:-mlo/mlo-base}"
TAG="${TAG:-uv1}"
LDAP_USERNAME="${LDAP_USERNAME:-you}" # TODO: Replace with your EPFL username
LDAP_UID=${LDAP_UID:-00000} # TODO: Replace with your LDAP UID (find it with: id -u)
LDAP_GROUPNAME="${LDAP_GROUPNAME:-MLO-unit}"
LDAP_GID="${LDAP_GID:-83070}"

echo "Building ${REGISTRY}/${IMAGE_PATH}:${TAG} with LDAP user ${LDAP_USERNAME} (${LDAP_UID}:${LDAP_GID})"
docker build . \
  --network=host \
  --build-arg LDAP_USERNAME="${LDAP_USERNAME}" \
  --build-arg LDAP_UID="${LDAP_UID}" \
  --build-arg LDAP_GROUPNAME="${LDAP_GROUPNAME}" \
  --build-arg LDAP_GID="${LDAP_GID}" \
  -t "${IMAGE_PATH}:${TAG}"

docker tag "${IMAGE_PATH}:${TAG}" "${REGISTRY}/${IMAGE_PATH}:${TAG}"
docker push "${REGISTRY}/${IMAGE_PATH}:${TAG}"
