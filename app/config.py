from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    groq_api_key: str
    webhook_secret: str
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    chunk_size: int = 800
    chunk_overlap: int = 100
    top_k: int = 4
    # Measured on the sample docs: answerable questions scored 0.67-0.83, an off-topic
    # one 0.38. Related-but-unanswerable questions score higher (0.65), so those rely
    # on the LLM replying NOT_FOUND instead.
    min_similarity: float = 0.5
    groq_model: str = "openai/gpt-oss-120b"


settings = Settings()
