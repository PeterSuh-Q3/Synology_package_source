FROM python:3.12-alpine
RUN apk add --no-cache curl ca-certificates
WORKDIR /app
COPY app.py ./
COPY landing.html ./
COPY tools ./tools
COPY data ./data
ENV PYTHONUNBUFFERED=1 PORT=8765 SYNC_RELEASES=1
EXPOSE 8765
CMD ["python", "app.py"]
