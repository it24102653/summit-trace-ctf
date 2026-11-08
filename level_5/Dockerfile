# =====================================================
# WEB-05 : "Basecamp Systems"  -  Moderate
# =====================================================
# server.py uses ONLY the Python standard library - no Flask,
# no pip install, no apt-get at container-build time. Both
# challenge assets (the permissions-audit tarball, built with
# real chmod'd files, and the compiled radio_lock ELF binary)
# are embedded as base64 strings in assets_data.py, generated
# offline - the running container never needs gcc, tar, or
# steghide-style build tools installed.

FROM python:3.12-slim

WORKDIR /app
COPY site/server.py .
COPY site/assets_data.py .

EXPOSE 8000

CMD ["python3", "server.py"]
