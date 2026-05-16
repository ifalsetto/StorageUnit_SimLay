from app.services.vision.mock_provider import MockVisionProvider
from app.services.vision.openai_provider import OpenAIVisionProvider


def get_vision_provider(config: dict, provider_name: str | None = None):
    provider = provider_name or config["app_config"]["vision"].get("default_provider", "openai")
    if provider == "openai":
        model = config.get("connectors", {}).get("vision_providers", {}).get("openai", {}).get("model", "gpt-4o-mini")
        return OpenAIVisionProvider(model=model)
    if provider == "mock":
        return MockVisionProvider()
    raise ValueError(f"Unsupported vision provider: {provider}")
