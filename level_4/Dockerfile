# =====================================================
# WEB-04 : "The Sealed Envelope"  -  Moderate
# =====================================================
# server.py uses ONLY the Python standard library - no Flask,
# no pip install, no apt-get at container-build time. The
# challenge image (with the steganographic payload already
# embedded via steghide at build time, offline) is bundled as
# a base64 string in image_data.py, so the running container
# never needs steghide installed - only the PLAYER's own Kali
# machine needs steghide to extract the hidden message.

FROM python:3.12-slim

WORKDIR /app
COPY site/server.py .
COPY site/image_data.py .

EXPOSE 8000

CMD ["python3", "server.py"]
