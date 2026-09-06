# Architecture

```text
Caller
  → Twilio phone number
  → Twilio bidirectional Media Stream
  → Pipecat Cloud agent
      → business hours: Twilio redirects to the owner
      → after hours: Deepgram STT → OpenRouter LLM → Deepgram TTS
      → completed enquiry: Cloudflare Email Service
```

`bot.py` is the process entry point. `receptionist/app.py` assembles the Pipecat pipeline
and owns the call lifecycle. `receptionist/tools.py` contains the actions available to the
model. Provider HTTP calls stay in `receptionist/twilio.py` and `receptionist/email.py`.
Deployment orchestration stays in `scripts/setup.py`; `scripts/twilio.py` owns Twilio number
provisioning.

Configuration enters through environment variables parsed by `receptionist/config.py`.
No workflow state or credentials live outside the code and deployment environment.
