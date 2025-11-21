from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Optional, Union

import streamlit as st

try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover - handled at runtime
    genai = None


DEFAULT_MODEL = "gemini-2.0-flash-lite"
DEFAULT_TEMPERATURE = 0.2
MAX_TOKENS = 1024
MIN_REQUEST_INTERVAL = 2  # Segundos mínimos entre solicitudes para evitar rate limiting


class GeminiConfigError(RuntimeError):
    """Error lanzado cuando la API de Gemini no está configurada."""


def _get_api_key() -> Optional[str]:
    return (
        st.secrets.get("GEMINI_API_KEY")
        if hasattr(st, "secrets")
        else None
    ) or os.getenv("GEMINI_API_KEY")


def _get_model_name() -> str:
    return (
        st.secrets.get("GEMINI_MODEL")
        if hasattr(st, "secrets")
        else None
    ) or os.getenv("GEMINI_MODEL") or DEFAULT_MODEL


@st.cache_resource(show_spinner=False)
def _load_model(model_name: str):
    api_key = _get_api_key()
    if not api_key:
        raise GeminiConfigError(
            "Configura GEMINI_API_KEY en .streamlit/secrets.toml o como variable de entorno."
        )
    if genai is None:
        raise GeminiConfigError(
            "El paquete google-generativeai no está instalado. Ejecuta `pip install -r requirements.txt`."
        )

    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name=model_name)


def _format_context(context: Dict[str, Any]) -> str:
    """Evita dumps gigantes truncando listas/tablas."""
    def _trim(value: Any, depth: int = 0) -> Any:
        if depth > 3:
            return "...(truncado)..."
        if isinstance(value, dict):
            return {k: _trim(v, depth + 1) for k, v in list(value.items())[:12]}
        if isinstance(value, list):
            trimmed = [_trim(v, depth + 1) for v in value[:8]]
            if len(value) > 8:
                trimmed.append("...(más filas truncadas)...")
            return trimmed
        return value

    safe_ctx = _trim(context)
    return json.dumps(safe_ctx, ensure_ascii=False, indent=2)


def build_prompt(context: Dict[str, Any], question: str) -> str:
    context_str = _format_context(context)
    instructions = (
        "Eres un analista financiero. Resume o responde basándote SOLO en el contexto "
        "proporcionado. Si no hay datos suficientes, indícalo claramente. y SIEMPRE cita los datos de la fuente. En caso de que no haya datos, indica que no hay datos suficientes."
        "NO INVENTES DATOS. SIEMPRE CITA LOS DATOS DE LA FUENTE. SOLO RESPONDE EN ESPAÑOL."
    )
    return f"{instructions}\n\nContexto del dashboard:\n{context_str}\n\nPregunta del usuario:\n{question.strip()}"


def call_gemini(
    context: Dict[str, Any],
    question: str,
    *,
    temperature: float = DEFAULT_TEMPERATURE,
    model_name: Optional[str] = None,
    max_retries: int = 3,
) -> str:
    """
    Llama a la API de Gemini con retry automático para errores 429 (rate limit).
    
    Args:
        context: Contexto del dashboard
        question: Pregunta del usuario
        temperature: Temperatura para la generación
        model_name: Nombre del modelo (opcional)
        max_retries: Número máximo de reintentos (default: 3)
    
    Returns:
        Respuesta de texto de Gemini
    
    Raises:
        RuntimeError: Si falla después de todos los reintentos o por otro error
    """
    prompt = build_prompt(context, question)
    model_id = model_name or _get_model_name()
    model = _load_model(model_id)
    
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            response = model.generate_content(
                [prompt],
                generation_config=genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=MAX_TOKENS,
                ),
            )
            
            # Si llegamos aquí, la llamada fue exitosa
            if hasattr(response, "text") and response.text:
                return response.text.strip()

            # Fallback manual para extraer texto
            parts: list[str] = []
            for candidate in getattr(response, "candidates", []):
                content = getattr(candidate, "content", None)
                if not content:
                    continue
                for part in getattr(content, "parts", []):
                    text = getattr(part, "text", None)
                    if text:
                        parts.append(text)

            if not parts:
                raise RuntimeError("Gemini no devolvió texto utilizable.")
            return "\n\n".join(part.strip() for part in parts if part.strip())
            
        except Exception as exc:
            last_error = exc
            error_str = str(exc)
            
            # Detectar error 429 (rate limit / quota exceeded)
            is_rate_limit = (
                "429" in error_str or
                "Resource exhausted" in error_str or
                "quota" in error_str.lower() or
                "rate limit" in error_str.lower()
            )
            
            if is_rate_limit and attempt < max_retries:
                # Backoff exponencial: 2^attempt segundos (2, 4, 8 segundos)
                wait_time = 2 ** attempt
                if attempt > 0:  # No mostrar mensaje en el primer intento
                    st.warning(
                        f"⏳ Límite de solicitudes alcanzado. Reintentando en {wait_time} segundos... "
                        f"(Intento {attempt + 1}/{max_retries + 1})"
                    )
                time.sleep(wait_time)
                continue
            else:
                # Si no es rate limit o ya agotamos los reintentos, lanzar error
                if is_rate_limit:
                    raise RuntimeError(
                        f"Error 429: Límite de solicitudes excedido. "
                        f"Por favor, espera unos minutos antes de intentar nuevamente. "
                        f"Detalles: {error_str}"
                    ) from exc
                else:
                    raise RuntimeError(f"Error al invocar Gemini: {error_str}") from exc
    
    # Si llegamos aquí, agotamos todos los reintentos
    raise RuntimeError(
        f"Error después de {max_retries + 1} intentos: {last_error}"
    ) from last_error


def _simulate_answer(question: str, context: Dict[str, Any]) -> str:
    metrics = context.get("metrics") or context.get("kpis") or {}
    highlights = ", ".join(f"{k}: {v}" for k, v in list(metrics.items())[:4])
    return (
        f"[Simulación] Respondería a: '{question}'.\n"
        f"Métricas clave detectadas: {highlights or 'sin métricas reportadas'}.\n"
        "Configura GEMINI_API_KEY para obtener respuestas reales."
    )


ContextSource = Union[Dict[str, Any], Callable[[], Dict[str, Any]]]


def _resolve_context(context_source: ContextSource) -> Dict[str, Any]:
    context = context_source() if callable(context_source) else context_source
    return context or {"message": "No hay datos disponibles para esta vista."}


def render_llm_assistant(
    page_id: str,
    context_source: ContextSource,
    *,
    title: str = "🤖 Asistente Gemini",
    help_text: str = "Pide un resumen o haz una pregunta sobre los datos filtrados.",
    default_question: str = "Dame un resumen ejecutivo del estado actual.",
    presets: Optional[Iterable[str]] = None,
):
    """Dibuja un panel reutilizable con entrada de texto y manejo de respuestas."""
    prompt_key = f"{page_id}_llm_prompt"
    dry_run_key = f"{page_id}_llm_dry_run"
    result_key = f"{page_id}_llm_result"
    last_request_key = f"{page_id}_llm_last_request_time"

    if prompt_key not in st.session_state:
        st.session_state[prompt_key] = default_question

    presets = list(presets or [])

    with st.expander(title, expanded=False):
        st.caption(help_text)

        if presets:
            cols = st.columns(len(presets))
            for idx, preset in enumerate(presets):
                if cols[idx].button(preset, key=f"{page_id}_preset_{idx}"):
                    st.session_state[prompt_key] = preset

        st.text_area(
            "Pregunta / instrucción",
            key=prompt_key,
            height=120,
        )

        st.checkbox(
            "Modo simulación (sin llamar a la API)",
            key=dry_run_key,
            value=st.session_state.get(dry_run_key, False),
            help="Útil para pruebas o cuando no tienes la API key configurada.",
        )

        if st.button("Consultar Gemini", key=f"{page_id}_llm_button"):
            question = st.session_state.get(prompt_key, "").strip()
            if not question:
                st.warning("Escribe una pregunta o selecciona una plantilla.")
                return

            # Throttling: asegurar delay mínimo entre solicitudes
            current_time = time.time()
            last_request_time = st.session_state.get(last_request_key, 0)
            time_since_last = current_time - last_request_time
            
            if time_since_last < MIN_REQUEST_INTERVAL:
                wait_time = MIN_REQUEST_INTERVAL - time_since_last
                st.warning(f"⏳ Por favor espera {wait_time:.1f} segundos antes de hacer otra solicitud.")
                time.sleep(wait_time)
            
            st.session_state[last_request_key] = time.time()

            context = _resolve_context(context_source)
            with st.spinner("Preguntando a Gemini..."):
                try:
                    if st.session_state.get(dry_run_key):
                        answer = _simulate_answer(question, context)
                    else:
                        answer = call_gemini(context, question)
                except GeminiConfigError as cfg_err:
                    st.error(f"❌ **Error de configuración:** {cfg_err}")
                    answer = f"No se pudo inicializar Gemini: {cfg_err}"
                except RuntimeError as rt_err:
                    error_msg = str(rt_err)
                    if "429" in error_msg or "Límite de solicitudes" in error_msg:
                        st.error(
                            "⚠️ **Límite de solicitudes alcanzado**\n\n"
                            "Has excedido el límite de solicitudes de la API de Gemini. "
                            "Por favor:\n"
                            "- Espera 1-2 minutos antes de intentar nuevamente\n"
                            "- Reduce la frecuencia de consultas\n"
                            "- Considera usar el modo simulación para pruebas"
                        )
                    else:
                        st.error(f"❌ **Error al procesar la solicitud:** {error_msg}")
                    answer = f"Error: {error_msg}"
                except Exception as exc:  # pragma: no cover - feedback runtime
                    st.error(f"❌ **Error inesperado:** {exc}")
                    answer = f"Error al procesar la solicitud: {exc}"

            st.session_state[result_key] = {"question": question, "answer": answer, "context": context}

        result = st.session_state.get(result_key)
        if result:
            st.markdown("#### Última respuesta")
            st.markdown(f"**Pregunta:** {result['question']}")
            st.write(result["answer"])
            with st.expander("Contexto enviado", expanded=False):
                st.code(_format_context(result["context"]), language="json")


__all__ = [
    "render_llm_assistant",
    "call_gemini",
    "build_prompt",
    "GeminiConfigError",
]


