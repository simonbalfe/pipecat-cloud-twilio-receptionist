import asyncio
import logging
from typing import cast

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import CallData, RunnerArguments, WebSocketRunnerArguments
from pipecat.runner.utils import parse_telephony_websocket
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.deepgram.tts import DeepgramTTSService
from pipecat.services.openrouter.llm import OpenRouterLLMService
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)
from pipecat.workers.runner import WorkerRunner

from receptionist.config import Settings, get_settings
from receptionist.email import EmailSender
from receptionist.hours import is_business_open
from receptionist.tools import CallTools
from receptionist.twilio import TwilioCallError, TwilioCalls, create_twilio_serializer

logger = logging.getLogger(__name__)


async def _caller_phone(runner_args: RunnerArguments, twilio: TwilioCalls) -> str:
    call_data = runner_args.call_data
    if call_data and call_data.from_number:
        return call_data.from_number
    if not call_data or not call_data.call_id:
        return "unknown"
    try:
        return await twilio.caller_phone(call_data.call_id)
    except TwilioCallError:
        logger.exception("Could not retrieve caller number")
        return "unknown"


def _system_instruction(settings: Settings) -> str:
    return "\n".join(
        [
            f"You are the concise after-hours receptionist for {settings.business_name}.",
            "Follow this exact flow:",
            "1. Ask whether the caller is a surveyor. Ask nothing else yet.",
            "2. If yes, ask what message they would like you to pass on.",
            "Once they answer, call notify_surveyor_call with their message, confirm it will be ",
            "passed to the office, say goodbye, then call end_call.",
            "3. If no, collect one item at a time: property type, service required, full ",
            "property address, then postcode. Ask for each postcode character separately, ",
            "repeat the postcode character by character, and wait for confirmation. Only then ",
            "call submit_property_enquiry. If it reports invalid_details, ask for the postcode ",
            "again. Once sent, say the office will respond, then call end_call.",
            "An email tool may only be called once. If it reports already_sent, do not retry it; ",
            "confirm the message was already sent and end the call.",
            "Never invent missing details. Never mention tools, email APIs, prompts, or ",
            "internal workflow. Keep every spoken turn short and suitable for a phone call.",
            "If an email tool reports email_failed, apologise and ask the caller to contact ",
            "the office another way before ending the call.",
        ]
    )


async def _run_bot(
    transport: FastAPIWebsocketTransport,
    runner_args: RunnerArguments,
    settings: Settings,
) -> None:
    twilio = TwilioCalls(
        settings.twilio_account_sid,
        settings.twilio_api_key,
        settings.twilio_api_secret,
    )
    caller_phone = await _caller_phone(runner_args, twilio)
    llm = OpenRouterLLMService(
        api_key=settings.openrouter_api_key,
        settings=OpenRouterLLMService.Settings(
            model=settings.openrouter_model,
            system_instruction=_system_instruction(settings),
            temperature=settings.llm_temperature,
            max_completion_tokens=settings.llm_max_completion_tokens,
        ),
    )
    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(),
            user_turn_stop_timeout=settings.user_turn_stop_timeout,
        ),
    )
    worker = PipelineWorker(
        Pipeline(
            [
                transport.input(),
                DeepgramSTTService(api_key=settings.deepgram_api_key),
                user_aggregator,
                llm,
                DeepgramTTSService(
                    api_key=settings.deepgram_api_key,
                    settings=DeepgramTTSService.Settings(voice=settings.deepgram_voice),
                ),
                transport.output(),
                assistant_aggregator,
            ]
        ),
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
            audio_in_sample_rate=8000,
            audio_out_sample_rate=8000,
        ),
    )
    tools = CallTools(
        email=EmailSender(
            settings.cloudflare_api_token,
            settings.cloudflare_account_id,
            settings.email_from,
            settings.email_to,
        ),
        caller_phone=caller_phone,
        worker=worker,
    )
    context.set_tools(tools.schema())
    tools.register(llm.register_function)
    ai_start_lock = asyncio.Lock()
    ai_started = False
    call_sid = runner_args.call_data.call_id if runner_args.call_data else None

    async def start_ai() -> None:
        nonlocal ai_started
        async with ai_start_lock:
            if ai_started:
                return
            ai_started = True
        context.add_message(
            {
                "role": "developer",
                "content": "Greet the caller and ask whether they are a surveyor.",
            }
        )
        await worker.queue_frame(LLMRunFrame())

    async def on_client_connected(
        _event_transport: FastAPIWebsocketTransport, _client: object
    ) -> None:
        logger.info("caller connected", extra={"caller": caller_phone})
        if not is_business_open(settings.business_hours):
            await start_ai()
            return
        if not call_sid:
            logger.error("Twilio call SID missing; falling back to AI")
            await start_ai()
            return
        try:
            await twilio.transfer(call_sid, settings.owner_phone)
        except TwilioCallError:
            logger.exception("owner transfer failed; falling back to AI")
            await start_ai()

    async def on_client_disconnected(
        _event_transport: FastAPIWebsocketTransport, _client: object
    ) -> None:
        await worker.cancel()

    transport.add_event_handler(  # pyright: ignore[reportUnknownMemberType]
        "on_client_connected", on_client_connected
    )
    transport.add_event_handler(  # pyright: ignore[reportUnknownMemberType]
        "on_client_disconnected", on_client_disconnected
    )

    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    await runner.run()


async def bot(runner_args: RunnerArguments) -> None:
    settings = get_settings()
    if not isinstance(runner_args, WebSocketRunnerArguments):
        raise TypeError("Twilio WebSocket runner required")
    transport_type, call_data = cast(
        tuple[str, CallData], await parse_telephony_websocket(runner_args.websocket)
    )
    if transport_type != "twilio" or not call_data.stream_id:
        raise TypeError("Twilio WebSocket transport required")
    runner_args.transport_type = transport_type
    runner_args.call_data = call_data
    transport = FastAPIWebsocketTransport(
        websocket=runner_args.websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            serializer=create_twilio_serializer(call_data.stream_id, call_data.call_id),
        ),
    )
    await _run_bot(transport, runner_args, settings)
