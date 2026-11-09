# The smallest image VS Code fully supports for decompdecomp. Debian slim: VS Code Server needs glibc, libstdc++,
# ca-certificates and tar (code.visualstudio.com/docs/remote/linux), all already in python:slim. Alpine is smaller
# but musl: extensions with native code break there, and so do decompdecomp's pinned compilers (glibc builds).
FROM python:3.12-slim-trixie

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv

# A network that inspects TLS: put its root CA in .devcontainer/certs/ as a .crt (ignored by git), and Python, uv
# and git trust it. Without one this does nothing.
COPY certs/ /usr/local/share/ca-certificates/devcontainer/

# All steps are in one layer. This layer installs these packages:
# - git: VS Code uses git for source control. decompdecomp uses git to clone public decomps.
# - bubblewrap: decompdecomp runs each compile in a bubblewrap sandbox. The sandbox also gives old 32-bit
#   compilers (for example the PS2 compilers ee-gcc 2.9x) the 32-bit loader at /lib/ld-linux.so.2.
#   The container does not have this loader. Without bubblewrap, these compilers do not start.
#   The error is "No such file or directory".
# Do not install compilers or their 32-bit runtime with apt. decompdecomp installs them with fixed versions
# and checksums (toolchains.toml).
# Then the layer adds the root CA of the network. It also adds a user (VS Code sets its uid to your uid) and the
# folders that the volumes in devcontainer.json keep.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git bubblewrap \
    && update-ca-certificates \
    && useradd -m -s /bin/bash -u 1000 vscode \
    && mkdir -p /home/vscode/Decomp-dev /home/vscode/.local/share/decompnet \
    && chown -R vscode:vscode /home/vscode \
    && rm -rf /var/lib/apt/lists/*

# the venv stays in the container, not in the workspace (a Windows checkout may have its own .venv there)
ENV UV_PROJECT_ENVIRONMENT=/home/vscode/.venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_SYSTEM_CERTS=1 \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

USER vscode
