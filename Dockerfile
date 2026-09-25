FROM node:24-slim AS fe
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm config set registry https://registry.npmmirror.com && npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
COPY app ./app
COPY static ./static
COPY --from=fe /fe/dist ./frontend/dist
ENV BANK_DB=/data/bank.db
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
