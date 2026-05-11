# mspepsearch: Wine + MSPepSearch64 for metabolomics spectral search
#
# Build context expects:
#   ./binaries/MSPepSearch.zip   (from NIST)
#
# Build:
#   docker build -f mspepsearch-container/Dockerfile -t mspepsearch:latest mspepsearch-container/
#
# Convert to Apptainer on Longleaf:
#   docker save mspepsearch:latest -o mspepsearch.tar
#   scp mspepsearch.tar longleaf:/work/users/j/a/jaileru/containers/
#   ssh longleaf
#   apptainer build mspepsearch.sif docker-archive://mspepsearch.tar

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    WINEDEBUG=-all \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# wine64 binary lives in the `wine` package on Ubuntu 22.04; wine64 alone is a libs-only split.
# xvfb provides a virtual display so wineboot can run headlessly during the build.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        wine \
        wine64 \
        xvfb \
        unzip \
        rsync \
        ca-certificates \
        procps \
        python3 && \
    rm -rf /var/lib/apt/lists/*

# Stage NIST binary
COPY mspepsearch-container/binaries/MSPepSearch.zip /tmp/MSPepSearch.zip

RUN mkdir -p /opt/mspepsearch && \
    unzip -o /tmp/MSPepSearch.zip -d /tmp/mspepsearch_unzip && \
    mv /tmp/mspepsearch_unzip/2024_03_15_MSPepSearch_x64/* /opt/mspepsearch/ && \
    rm -rf /tmp/MSPepSearch.zip /tmp/mspepsearch_unzip && \
    chmod -R a+rx /opt/mspepsearch

# Pre-initialize the 64-bit Wine prefix.
# xvfb-run supplies a virtual framebuffer; WINEDLLOVERRIDES suppresses the menu-builder GUI.
ENV WINEPREFIX=/opt/wine64 WINEARCH=win64
RUN WINEDLLOVERRIDES="winemenubuilder.exe=d" xvfb-run wineboot --init && \
    wineserver -w && \
    chmod -R a+rx /opt/wine64

ENV WINEPREFIX= WINEARCH=

ENV PATH=/opt/mspepsearch:$PATH

COPY mspepsearch-container/binaries/run_with_wine_prefix.sh /usr/local/bin/run_with_wine_prefix.sh
RUN chmod +x /usr/local/bin/run_with_wine_prefix.sh

WORKDIR /work
CMD ["/bin/bash"]