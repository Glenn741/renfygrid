FROM python:3.12-slim
WORKDIR /app
COPY renmeter_common/ renmeter_common/
COPY dummy_config_loader.py dummy_config_reader.py ./
ENTRYPOINT ["python", "dummy_config_reader.py"]
