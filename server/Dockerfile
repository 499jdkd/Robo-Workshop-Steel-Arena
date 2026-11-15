FROM python:3.13-slim
WORKDIR /app
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server/ server/
COPY src/armory.py src/combat_rules.py src/robot_designs.py src/
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "-m", "server.run"]
