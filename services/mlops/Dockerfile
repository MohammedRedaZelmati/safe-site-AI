FROM ghcr.io/mlflow/mlflow:v3.15.2@sha256:fdcc147a5c4ea47842b81b2f420815687ddfe37144299ec437009e60b783cf5c

CMD ["mlflow", "server", "--backend-store-uri", "sqlite:////data/mlflow/mlflow.db", "--default-artifact-root", "file:///data/mlflow/artifacts", "--host", "0.0.0.0", "--port", "5000"]
