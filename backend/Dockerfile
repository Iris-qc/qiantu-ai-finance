FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
# 迁移与种子数据由 docker-compose 的 command 执行
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
