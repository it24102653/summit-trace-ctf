# =====================================================
# WEB-03 : "ShopNest Order Leak"  -  Moderate
# =====================================================
# server.py uses ONLY the Python standard library - no Flask,
# no pip install, no apt-get. Only the base python:3.12-slim
# image itself needs to be pulled, avoiding the network/TLS
# issues seen with other images and package installs.

FROM python:3.12-slim

WORKDIR /app
COPY site/server.py .

EXPOSE 8000

CMD ["python3", "server.py"]
