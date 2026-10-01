import os
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from api.services.configuration.registry import (
    DeepgramSTTConfiguration,
    DeepgramTTSConfiguration,
    DograhEmbeddingsConfiguration,
    DograhLLMService,
    DograhSTTService,
    DograhTTSService,
    ElevenlabsTTSConfiguration,
    EmbeddingsConfig,
    GoogleLLMService,
    GoogleRealtimeLLMConfiguration,
    GoogleSTTConfiguration,
    GoogleTTSConfiguration,
    GroqLLMService,
    LLMConfig,
    OpenAIEmbeddingsConfiguration,
    OpenAILLMService,
    OpenAIRealtimeLLMConfiguration,
    RealtimeConfig,
    SarvamLLMConfiguration,
    SarvamSTTConfiguration,
    SarvamTTSConfiguration,
    ServiceProviders,
    SmallestAITTSConfiguration,
    STTConfig,
    TTSConfig,
)

DOGRAH_SPEED_MIN = 0.5
DOGRAH_SPEED_MAX = 2.0
DOGRAH_SPEED_STEP = 0.1
DOGRAH_SPEED_OPTIONS: tuple[float, ...] = (0.8, 1.0, 1.2)
DOGRAH_DEFAULT_VOICE = "default"
DOGRAH_DEFAULT_LANGUAGE = "multi"


class EffectiveAIModelConfiguration(BaseModel):
    llm: LLMConfig | None = None
    stt: STTConfig | None = None
    tts: TTSConfig | None = None
    embeddings: EmbeddingsConfig | None = None
    realtime: RealtimeConfig | None = None
    is_realtime: bool = False
    managed_service_version: int | None = None
    test_phone_number: str | None = None
    timezone: str | None = None
    last_validated_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def strip_incomplete_realtime_when_disabled(cls, data):
        """Skip realtime validation when is_realtime is False and api_key is missing."""
        if isinstance(data, dict) and not data.get("is_realtime", False):
            realtime = data.get("realtime")
            if isinstance(realtime, dict) and not realtime.get("api_key"):
                data.pop("realtime", None)
        return data


class DograhManagedAIModelConfiguration(BaseModel):
    api_key: str = ""
    voice: str = DOGRAH_DEFAULT_VOICE
    speed: float = Field(default=1.0, ge=DOGRAH_SPEED_MIN, le=DOGRAH_SPEED_MAX)
    language: str = DOGRAH_DEFAULT_LANGUAGE
    llm_provider: str = ServiceProviders.DOGRAH.value
    llm_model: str = "default"
    tts_provider: str = ServiceProviders.DOGRAH.value
    tts_model: str = "default"
    stt_provider: str = ServiceProviders.DOGRAH.value
    stt_model: str = "default"
    realtime_provider: str | None = None
    realtime_model: str | None = None
    embeddings_provider: str | None = ServiceProviders.DOGRAH.value
    embeddings_model: str | None = "dograh_embedding_v1"


class BYOKPipelineAIModelConfiguration(BaseModel):
    llm: LLMConfig
    tts: TTSConfig
    stt: STTConfig
    embeddings: EmbeddingsConfig | None = None

    @model_validator(mode="after")
    def reject_dograh_providers(self):
        _reject_dograh_provider("llm", self.llm)
        _reject_dograh_provider("tts", self.tts)
        _reject_dograh_provider("stt", self.stt)
        _reject_dograh_provider("embeddings", self.embeddings)
        return self


class BYOKRealtimeAIModelConfiguration(BaseModel):
    realtime: RealtimeConfig
    llm: LLMConfig
    embeddings: EmbeddingsConfig | None = None
    stt: STTConfig | None = None

    @model_validator(mode="after")
    def reject_dograh_providers(self):
        _reject_dograh_provider("llm", self.llm)
        _reject_dograh_provider("embeddings", self.embeddings)
        _reject_dograh_provider("stt", self.stt)
        return self


class BYOKAIModelConfiguration(BaseModel):
    mode: Literal["pipeline", "realtime"]
    pipeline: BYOKPipelineAIModelConfiguration | None = None
    realtime: BYOKRealtimeAIModelConfiguration | None = None

    @model_validator(mode="after")
    def validate_selected_mode(self):
        if self.mode == "pipeline" and self.pipeline is None:
            raise ValueError("byok.pipeline is required when byok.mode is pipeline")
        if self.mode == "realtime" and self.realtime is None:
            raise ValueError("byok.realtime is required when byok.mode is realtime")
        return self


class OrganizationAIModelConfigurationV2(BaseModel):
    version: Literal[2] = 2
    mode: Literal["dograh", "byok"]
    dograh: DograhManagedAIModelConfiguration | None = None
    byok: BYOKAIModelConfiguration | None = None

    @model_validator(mode="after")
    def validate_selected_mode(self):
        if self.mode == "dograh" and self.dograh is None:
            raise ValueError("dograh configuration is required when mode is dograh")
        if self.mode == "byok" and self.byok is None:
            raise ValueError("byok configuration is required when mode is byok")
        return self


class OrganizationAIModelConfigurationResponse(BaseModel):
    configuration: dict | None
    effective_configuration: dict
    source: Literal["organization_v2", "legacy_user_v1", "empty"]


def compile_ai_model_configuration_v2(
    configuration: OrganizationAIModelConfigurationV2,
) -> EffectiveAIModelConfiguration:
    if configuration.mode == "dograh":
        if configuration.dograh is None:
            raise ValueError("dograh configuration is required")
        return _compile_dograh_configuration(configuration.dograh)

    if configuration.byok is None:
        raise ValueError("byok configuration is required")
    if configuration.byok.mode == "pipeline":
        if configuration.byok.pipeline is None:
            raise ValueError("byok.pipeline is required")
        pipeline = configuration.byok.pipeline
        return EffectiveAIModelConfiguration(
            llm=pipeline.llm,
            tts=pipeline.tts,
            stt=pipeline.stt,
            embeddings=pipeline.embeddings,
            is_realtime=False,
        )

    if configuration.byok.realtime is None:
        raise ValueError("byok.realtime is required")
    realtime = configuration.byok.realtime
    return EffectiveAIModelConfiguration(
        llm=realtime.llm,
        realtime=realtime.realtime,
        embeddings=realtime.embeddings,
        stt=realtime.stt,
        is_realtime=True,
    )


def _get_system_key(provider: str | ServiceProviders, fallback: str = "") -> str:
    p = provider.value if isinstance(provider, ServiceProviders) else str(provider)
    env_keys = {
        "google": os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", ""),
        "sarvam": os.environ.get("SARVAM_API_KEY", ""),
        "groq": os.environ.get("GROQ_API_KEY", ""),
        "openai": os.environ.get("OPENAI_API_KEY", ""),
        "openrouter": os.environ.get("OPENROUTER_API_KEY", ""),
        "deepgram": os.environ.get("DEEPGRAM_API_KEY", ""),
        "elevenlabs": os.environ.get("ELEVENLABS_API_KEY", ""),
        "smallest": os.environ.get("SMALLEST_API_KEY", ""),
        "google_realtime": os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", ""),
        "openai_realtime": os.environ.get("OPENAI_API_KEY", ""),
    }
    return fallback or env_keys.get(p, "")


def _compile_dograh_configuration(
    configuration: DograhManagedAIModelConfiguration,
) -> EffectiveAIModelConfiguration:
    # 1. LLM
    llm_prov = configuration.llm_provider or ServiceProviders.DOGRAH.value
    llm_model = configuration.llm_model or "default"
    llm_key = _get_system_key(llm_prov, configuration.api_key)

    if llm_prov == ServiceProviders.GOOGLE.value:
        llm = GoogleLLMService(provider=ServiceProviders.GOOGLE, model=llm_model, api_key=llm_key)
    elif llm_prov == ServiceProviders.SARVAM.value:
        llm = SarvamLLMConfiguration(provider=ServiceProviders.SARVAM, model=llm_model, api_key=llm_key)
    elif llm_prov == ServiceProviders.GROQ.value:
        llm = GroqLLMService(provider=ServiceProviders.GROQ, model=llm_model, api_key=llm_key)
    elif llm_prov == ServiceProviders.OPENAI.value:
        llm = OpenAILLMService(provider=ServiceProviders.OPENAI, model=llm_model, api_key=llm_key)
    else:
        llm = DograhLLMService(provider=ServiceProviders.DOGRAH, api_key=configuration.api_key, model=llm_model)

    # 2. TTS
    tts_prov = configuration.tts_provider or ServiceProviders.DOGRAH.value
    tts_model = configuration.tts_model or "default"
    tts_key = _get_system_key(tts_prov, configuration.api_key)

    if tts_prov == ServiceProviders.SARVAM.value:
        tts = SarvamTTSConfiguration(
            provider=ServiceProviders.SARVAM,
            model=tts_model if tts_model != "default" else "bulbul:v2",
            voice=configuration.voice if configuration.voice != "default" else "anushka",
            language=configuration.language if configuration.language != "multi" else "hi-IN",
            api_key=tts_key,
        )
    elif tts_prov == ServiceProviders.DEEPGRAM.value:
        tts = DeepgramTTSConfiguration(
            provider=ServiceProviders.DEEPGRAM,
            voice=configuration.voice if configuration.voice != "default" else "aura-2-helena-en",
            api_key=tts_key,
        )
    elif tts_prov == ServiceProviders.ELEVENLABS.value:
        tts = ElevenlabsTTSConfiguration(
            provider=ServiceProviders.ELEVENLABS,
            voice=configuration.voice if configuration.voice != "default" else "21m00Tcm4TlvDq8ikWAM",
            model=tts_model if tts_model != "default" else "eleven_multilingual_v2",
            api_key=tts_key,
        )
    elif tts_prov == ServiceProviders.GOOGLE.value:
        tts = GoogleTTSConfiguration(
            provider=ServiceProviders.GOOGLE,
            model=tts_model if tts_model != "default" else "en-US-Journey-F",
            voice=configuration.voice if configuration.voice != "default" else "en-US-Journey-F",
            api_key=tts_key,
        )
    elif tts_prov == ServiceProviders.SMALLEST.value:
        tts = SmallestAITTSConfiguration(
            provider=ServiceProviders.SMALLEST,
            voice=configuration.voice if configuration.voice != "default" else "sophia",
            api_key=tts_key,
        )
    else:
        tts = DograhTTSService(
            provider=ServiceProviders.DOGRAH,
            api_key=configuration.api_key,
            model=tts_model,
            voice=configuration.voice,
            speed=configuration.speed,
        )

    # 3. STT
    stt_prov = configuration.stt_provider or ServiceProviders.DOGRAH.value
    stt_model = configuration.stt_model or "default"
    stt_key = _get_system_key(stt_prov, configuration.api_key)

    if stt_prov == ServiceProviders.SARVAM.value:
        stt = SarvamSTTConfiguration(
            provider=ServiceProviders.SARVAM,
            model=stt_model if stt_model != "default" else "saarika:v2.5",
            language=configuration.language if configuration.language != "multi" else "unknown",
            api_key=stt_key,
        )
    elif stt_prov == ServiceProviders.DEEPGRAM.value:
        stt = DeepgramSTTConfiguration(
            provider=ServiceProviders.DEEPGRAM,
            model=stt_model if stt_model != "default" else "nova-3-general",
            language=configuration.language,
            api_key=stt_key,
        )
    elif stt_prov == ServiceProviders.GOOGLE.value:
        stt = GoogleSTTConfiguration(
            provider=ServiceProviders.GOOGLE,
            model=stt_model if stt_model != "default" else "latest_long",
            language=configuration.language if configuration.language != "multi" else "en-US",
            api_key=stt_key,
        )
    else:
        stt = DograhSTTService(
            provider=ServiceProviders.DOGRAH,
            api_key=configuration.api_key,
            model=stt_model,
            language=configuration.language,
        )

    # 4. Realtime (optional speech-to-speech)
    is_realtime = False
    realtime = None
    if configuration.realtime_provider:
        is_realtime = True
        rt_prov = configuration.realtime_provider
        rt_model = configuration.realtime_model or "default"
        rt_key = _get_system_key(rt_prov, configuration.api_key)
        if rt_prov == ServiceProviders.GOOGLE_REALTIME.value:
            realtime = GoogleRealtimeLLMConfiguration(
                provider=ServiceProviders.GOOGLE_REALTIME,
                model=rt_model if rt_model != "default" else "gemini-2.0-flash-exp",
                api_key=rt_key,
            )
        elif rt_prov == ServiceProviders.OPENAI_REALTIME.value:
            realtime = OpenAIRealtimeLLMConfiguration(
                provider=ServiceProviders.OPENAI_REALTIME,
                model=rt_model if rt_model != "default" else "gpt-4o-realtime-preview",
                api_key=rt_key,
            )

    # 5. Embeddings
    emb_prov = configuration.embeddings_provider or ServiceProviders.DOGRAH.value
    emb_model = configuration.embeddings_model or "dograh_embedding_v1"
    emb_key = _get_system_key(emb_prov, configuration.api_key)
    if emb_prov == ServiceProviders.OPENAI.value:
        embeddings = OpenAIEmbeddingsConfiguration(
            provider=ServiceProviders.OPENAI,
            model=emb_model if emb_model != "default" else "text-embedding-3-small",
            api_key=emb_key,
        )
    else:
        embeddings = DograhEmbeddingsConfiguration(
            provider=ServiceProviders.DOGRAH,
            api_key=configuration.api_key,
            model=emb_model,
        )

    return EffectiveAIModelConfiguration(
        llm=llm,
        tts=tts,
        stt=stt,
        embeddings=embeddings,
        realtime=realtime,
        is_realtime=is_realtime,
        managed_service_version=2,
    )



def _reject_dograh_provider(section: str, service) -> None:
    if service is None:
        return
    if getattr(service, "provider", None) == ServiceProviders.DOGRAH:
        raise ValueError(f"BYOK {section} cannot use Dograh provider")
