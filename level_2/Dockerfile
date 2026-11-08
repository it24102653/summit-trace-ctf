# =====================================================
# WEB-02 : "The Hidden Admin Panel"  -  Easy-Moderate
# =====================================================
# server.py uses ONLY the Python standard library (http.server,
# uuid, json, urllib) - no Flask, no pip install, no apt-get.
# This avoids any repeat of the network/TLS issues seen pulling
# other images or packages: only the base python:3.12-slim
# image itself needs to be pulled.

FROM python:3.12-slim

WORKDIR /app
COPY site/server.py .

EXPOSE 8000

CMD ["python3", "server.py"]
