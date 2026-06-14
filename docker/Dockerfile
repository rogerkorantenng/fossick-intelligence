FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1

# System dependencies
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv \
    git curl wget unzip \
    libewf-dev libssl-dev ewf-tools \
    sleuthkit \
    yara \
    python3-dev build-essential \
    libbz2-dev libfuse-dev fuse \
    && rm -rf /var/lib/apt/lists/*

# Volatility 3
RUN pip3 install volatility3

# Plaso via apt (more reliable than pip on Ubuntu)
RUN apt-get update && apt-get install -y \
    python3-plaso plaso-tools \
    2>/dev/null || \
    pip3 install --no-deps dfvfs dfimagetools plaso 2>/dev/null || \
    echo "plaso via apt failed, using pip fallback"

# Ensure log2timeline.py is available
RUN which log2timeline.py 2>/dev/null || \
    pip3 install plaso 2>/dev/null || \
    ln -sf $(python3 -c "import site; print(site.getsitepackages()[0])")/plaso/cli/log2timeline_tool.py /usr/local/bin/log2timeline.py 2>/dev/null || \
    echo "log2timeline fallback attempted"

# Python forensics libs
RUN pip3 install \
    analyzeMFT \
    regipy \
    construct \
    pycryptodome \
    iocextract

# MCP server deps
COPY requirements.txt /tmp/mcp_requirements.txt
RUN pip3 install -r /tmp/mcp_requirements.txt

# YARA community rules
RUN mkdir -p /opt/yara-rules && \
    curl -sL https://github.com/Yara-Rules/rules/archive/refs/heads/master.zip \
    -o /tmp/yara.zip && \
    unzip -q /tmp/yara.zip -d /opt/yara-rules && \
    rm /tmp/yara.zip || true

WORKDIR /fossick
COPY ../mcp_server /fossick/mcp_server

ENV PYTHONPATH=/fossick

CMD ["python3", "-m", "mcp_server.server"]
