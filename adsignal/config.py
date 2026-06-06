from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # MongoDB
    mongo_uri: str = "mongodb://adsignal:adsignal@localhost:27017/adsignal?authSource=admin"
    mongo_db: str = "adsignal"

    # Iceberg / Lakekeeper
    iceberg_rest_uri: str = "http://localhost:8181/catalog"
    iceberg_warehouse: str = "s3://adsignal-warehouse/"
    iceberg_s3_endpoint: str = "http://localhost:9000"
    iceberg_s3_access_key: str = "minioadmin"
    iceberg_s3_secret_key: str = "minioadmin"

    # Spark
    spark_master: str = "local[*]"
    spark_app_name: str = "adsignal-etl"

    # LLM — model-agnostic
    llm_provider: str = Field(
        default="ollama",
        description="ollama | lmstudio | anthropic | openai",
    )
    llm_model: str = Field(default="llama3.2", description="model name for the chosen provider")
    ollama_base_url: str = "http://localhost:11434"
    lmstudio_base_url: str = "http://localhost:1234/v1"
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Meta Ad Library (optional — falls back to synthetic if not set)
    meta_api_token: str = ""
    meta_api_version: str = "v21.0"

    # App
    brands: list[str] = Field(
        default=["nike", "adidas", "apple", "samsung", "coca-cola"],
        description="brands to track"
    )
    log_level: str = "INFO"


settings = Settings()
