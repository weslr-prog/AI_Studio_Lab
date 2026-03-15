from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AgentModelConfig:
    primary_model: str
    fallback_models: tuple[str, ...]
    num_predict: int


class ModelGateway:
    def __init__(self) -> None:
        self._configs: dict[str, AgentModelConfig] = {
            "director": AgentModelConfig(
                primary_model="qwen2.5:7b",
                fallback_models=("qwen2.5:14b",),
                num_predict=512,
            ),
            "architect": AgentModelConfig(
                primary_model="qwen2.5-coder:14b",
                fallback_models=("qwen2.5:14b",),
                num_predict=768,
            ),
            "programmer": AgentModelConfig(
                primary_model="qwen2.5-coder:14b",
                fallback_models=("qwen2.5:14b",),
                num_predict=1536,
            ),
            "qa": AgentModelConfig(
                primary_model="qwen2.5:7b",
                fallback_models=("qwen2.5:14b",),
                num_predict=512,
            ),
        }

    def model_for(self, agent_name: str) -> str:
        config = self._configs.get(agent_name)
        if config is None:
            raise ValueError(f"Unknown agent_name for model gateway: {agent_name}")
        return config.primary_model

    def generate_json(self, agent_name: str, prompt: str) -> dict[str, Any]:
        config = self._configs.get(agent_name)
        if config is None:
            return {
                "agent": agent_name,
                "status": "error",
                "message": "Unknown model gateway agent",
            }

        try:
            from ollama import Client
        except Exception as exc:
            return {
                "agent": agent_name,
                "status": "error",
                "message": f"Ollama Python API unavailable: {exc}",
            }

        client = Client()
        candidates = (config.primary_model, *config.fallback_models)
        last_error = "Model generation failed"

        for model_name in candidates:
            try:
                response = client.generate(
                    model=model_name,
                    prompt=prompt,
                    format="json",
                    options={
                        "temperature": 0,
                        "top_p": 1,
                        "seed": 7,
                        "num_predict": config.num_predict,
                    },
                )
                if not hasattr(response, "response"):
                    return {
                        "agent": agent_name,
                        "status": "error",
                        "message": "Malformed Ollama GenerateResponse",
                    }
                return {
                    "agent": agent_name,
                    "status": "ok",
                    "model": model_name,
                    "response": str(response.response),
                }
            except Exception as exc:
                last_error = str(exc)
                if "not found" not in last_error.lower():
                    break

        return {
            "agent": agent_name,
            "status": "error",
            "message": last_error,
        }
