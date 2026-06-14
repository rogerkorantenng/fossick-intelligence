FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv \
    git curl wget unzip \
    libewf-dev libssl-dev \
    sleuthkit \
    yara \
    && rm -rf /var/lib/apt/lists/*

# Volatility 3
RUN pip3 install volatility3

# Plaso (log2timeline)
RUN pip3 install plaso || echo "plaso install attempted"

# EZ Tools Python equivalents
RUN pip3 install analyzeMFT regipy || echo "regipy install attempted"

# python-prefetch
RUN pip3 install python-prefetch || echo "prefetch install attempted"

# MCP server deps
COPY requirements.txt /tmp/mcp_requirements.txt
RUN pip3 install -r /tmp/mcp_requirements.txt

WORKDIR /fossick
COPY ../mcp_server /fossick/mcp_server

ENV PYTHONPATH=/fossick

CMD ["python3", "-m", "mcp_server.server"]
