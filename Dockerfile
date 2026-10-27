FROM python:3.12-alpine
WORKDIR /app
COPY prepare.py server.py ./
COPY player/ ./player/
ENV ISO_DIR=/isos DATA_DIR=/data PORT=8080 PYTHONUNBUFFERED=1
VOLUME ["/isos", "/data"]
EXPOSE 8080
CMD ["python", "/app/server.py"]
