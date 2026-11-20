FROM ghcr.io/home-assistant/base-python:3.14-alpine3.24

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN pip install --no-cache-dir \
        starlette==1.10.0 \
        uvicorn==0.54.0 \
        jinja2==3.1.6

WORKDIR /app
COPY app/ /app/
RUN chmod +x /app/run.sh

# Der Ingress-Proxy kommt von außerhalb des Containers auf die Container-IP,
# daher 0.0.0.0. Die Sperre auf 172.30.32.2 passiert in der Anwendung.
EXPOSE 8099

CMD ["/app/run.sh"]
