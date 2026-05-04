# nist-tools: Wine + lib2nist + MSPepSearch64 for metabolomics annotation
#
# Build context expects:
#   ./binaries/MSPepSearch64.zip   (from NIST)
#
# Build:
#   docker build -t nist-tools:latest .
#
# Convert to Apptainer on Longleaf:
#   docker save nist-tools:latest -o nist-tools.tar
#   scp nist-tools.tar longleaf:/work/users/j/a/jaileru/containers/
#   ssh longleaf
#   apptainer build nist-tools.sif docker-archive://nist-tools.tar

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
        cabextract \
        unzip \
        ca-certificates \
        procps \
        rsync \
        python3 \
        python3-pip && \
    rm -rf /var/lib/apt/lists/*

# Stage NIST binaries
COPY binaries/ /tmp/binaries/

RUN mkdir -p /opt/mspepsearch && \
    mkdir -p /opt/lib2nist && \
    cd /opt/mspepsearch && unzip -o /tmp/binaries/MSPepSearch.zip && \
    cd /opt/lib2nist && unzip -o /tmp/binaries/lib2nist.zip && \
    rm -rf /tmp/binaries && \
    chmod -R a+rX /opt/mspepsearch && \
    chmod -R a+rX /opt/lib2nist

# Pre-initialize the 64-bit Wine prefix used by both tools.
# xvfb-run supplies a virtual framebuffer; WINEDLLOVERRIDES suppresses the menu-builder GUI.
ENV WINEPREFIX=/opt/wine64 WINEARCH=win64
RUN WINEDLLOVERRIDES="winemenubuilder.exe=d" xvfb-run wineboot --init && \
    wineserver -w && \
    chmod -R a+rX /opt/wine64

# Reset env so callers must explicitly invoke via the helper
ENV WINEPREFIX= WINEARCH=

ENV PATH=/opt/mspepsearch/2024_03_15_MSPepSearch_x64:$PATH
ENV PATH=/opt/lib2nist/:$PATH
# Helper to copy the prefix to a writable location and exec a Wine command.
# Usage:
#   run_with_wine_prefix.sh <wine_command...>
COPY convert.ini /opt/lib2nist/convert.ini
COPY run_with_wine_prefix.sh /usr/local/bin/run_with_wine_prefix.sh
COPY lib2nist_convert.sh /usr/local/bin/lib2nist_convert.sh
RUN chmod +x /usr/local/bin/run_with_wine_prefix.sh \
             /usr/local/bin/lib2nist_convert.sh

WORKDIR /work
CMD ["/bin/bash"]