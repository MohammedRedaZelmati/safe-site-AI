from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://safesite:safesite_dev_password@localhost:5432/safesite"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

