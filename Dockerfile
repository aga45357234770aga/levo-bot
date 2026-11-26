FROM python:3.12-slim
WORKDIR /app
COPY . .
EXPOSE 8501
ENV PYTHONUNBUFFERED=1
CMD ["python", "web_server.py"]
