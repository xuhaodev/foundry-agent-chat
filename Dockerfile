# 基础镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 复制项目文件
COPY . .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 暴露端口（Chainlit 默认 8000）
EXPOSE 8000

# 启动应用
CMD ["python", "chainlit_app.py"]