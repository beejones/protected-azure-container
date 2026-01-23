# Protected Azure Container
# 
# This Dockerfile simply references the main build in docker/
# For the actual container definition, see docker/Dockerfile

FROM scratch
COPY --from=docker/Dockerfile / /
