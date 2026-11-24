from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./adrobot.db"
    keitaro_api_address: str = ""
    keitaro_api_key: str = ""
    keitaro_group_name: str = "Adrobot"
    keitaro_source_name: str = "Adrobot"
    keitaro_domain: str = ""
    keitaro_campaigns_path: str = "/campaigns"
    keitaro_streams_path: str = "/streams"
    keitaro_offers_path: str = "/offers"
    keitaro_groups_path: str = "/groups"
    keitaro_sources_path: str = "/traffic_sources"
    keitaro_domains_path: str = "/domains"
    keitaro_group_id: int = 10332
    keitaro_source_id: int = 836
    keitaro_domain_id: int = 1813

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")


settings = Settings()
