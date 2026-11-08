# =====================================================
# WEB-06 : "The Final Transmission"  -  Hard (capstone)
# =====================================================
# server.py uses ONLY the Python standard library - no Flask,
# no pip install, no apt-get at container-build time. The
# combined JPEG+ZIP+pcap asset was built offline (using PIL,
# scapy, and real zip/cat carving) and is embedded as a base64
# string in assets_data.py - the running container itself
# never needs PIL, scapy, binwalk, or tshark installed. Only
# the PLAYER's own Kali machine needs those tools to solve it.

FROM python:3.12-slim

WORKDIR /app
COPY site/server.py .
COPY site/assets_data.py .

EXPOSE 8000

CMD ["python3", "server.py"]
