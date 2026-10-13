from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_user: str = "dio"
    postgres_password: str = "dio"
    postgres_host: str = "localhost"
    postgres_port: int = 5433
    postgres_db: str = "dio"
    postgres_sslmode: str = "disable"

    jwt_secret: str = "cambia-esta-clave-jwt-de-desarrollo-dio"
    jwt_expire_minutes: int = 1440
    cors_origins: str = (
        "http://localhost:4200,http://127.0.0.1:4200,"
        "http://localhost:5173,http://localhost:3000"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{quote_plus(self.postgres_user)}:{quote_plus(self.postgres_password)}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            f"?sslmode={self.postgres_sslmode}"
        )


settings = Settings()
