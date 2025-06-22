import base64
import pandas as pd
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.providers.google_vertex import GoogleVertexProvider
from .settings import load_settings

settings = load_settings(env_dev=True)
vertex_provider = GoogleVertexProvider(
    project_id=settings.GCP_PROJECT_ID, region=settings.GCP_LOCATION
)


class ImageDescriptionAgent:
    def __init__(
        self,
        model_name: str = getattr(settings, "MODEL_NAME", "gemini-pro"),
        system_prompt: str = "אתה סוכן המתאר תמונות",
    ):
        self.model_name = model_name
        self.system_prompt = system_prompt
        self._extract_agent()

    def _extract_agent(self):
        model = GeminiModel(self.model_name, provider=vertex_provider)
        self.agent = Agent(model, system_prompt=self.system_prompt)

    def run(self, image_b64: str) -> str:
        image_bytes = base64.b64decode(image_b64)
        bc = BinaryContent(data=image_bytes, media_type="image/png")
        user_prompt = "תתאר מה אתה רואה בתמונה המצורפת?"
        result = self.agent.run_sync([user_prompt, bc])
        return result.data


class DataFrameDescriptionAgent:
    def __init__(
        self,
        model_name: str = getattr(settings, "MODEL_NAME", "gemini-pro"),
        system_prompt: str = "אתה סוכן המתאר טבלאות נתונים",
    ):
        self.model_name = model_name
        self.system_prompt = system_prompt
        self._extract_agent()

    def _extract_agent(self):
        model = GeminiModel(self.model_name, provider=vertex_provider)
        self.agent = Agent(model, system_prompt=self.system_prompt)

    def run(self, df: pd.DataFrame) -> str:
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        bc = BinaryContent(data=csv_bytes, media_type="text/csv")
        user_prompt = "תתאר במילים את כל התוכן בטבלה המצורפת"
        result = self.agent.run_sync([user_prompt, bc])
        return result.data
