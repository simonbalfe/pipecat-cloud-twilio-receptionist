# Pipecat Cloud Twilio Receptionist Template

A small, fully code-managed Python voice agent for Pipecat Cloud and Twilio. Fork it,
configure `.env`, deploy it, and point a Twilio number at the agent. See
[Architecture](docs/architecture.md) for the complete system in one diagram.

## Included workflow

1. During configured business hours, redirect the Twilio call to `OWNER_PHONE`.
2. Outside business hours, ask whether the caller is a surveyor.
3. Surveyors hear `SURVEYOR_MESSAGE`; the call is emailed to `EMAIL_TO`.
4. Other callers provide the property type, required service, and address; the enquiry is emailed to `EMAIL_TO`.
5. If the owner redirect request fails, fall back to the AI flow.

The workflow is ordinary Python in `receptionist/`. There is no visual workflow state.

## Accounts

- Pipecat Cloud
- Twilio Programmable Voice number
- Deepgram for speech-to-text and text-to-speech
- OpenRouter for the language model
- Resend for email

## Configure

```bash
cp .env.example .env
uv sync
```

Fill every value in `.env`. Change `agent_name` and `secret_set` in `pcc-deploy.toml`
before deploying your own copy.

## Check

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run python -m unittest discover -s tests
```

## Deploy

```bash
uv run pipecat cloud auth login
uv run pipecat cloud secrets set pipecat-twilio-receptionist-secrets --file .env
uv run pipecat cloud deploy --yes --build-dir .
uv run pipecat cloud organizations list
```

With `min_agents = 0`, the service scales to zero between calls.

## Connect Twilio

Create a TwiML Bin and replace `AGENT_NAME.ORGANIZATION_NAME`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="wss://api.pipecat.daily.co/ws/twilio">
      <Parameter
        name="_pipecatCloudServiceHost"
        value="AGENT_NAME.ORGANIZATION_NAME"
      />
    </Stream>
  </Connect>
</Response>
```

Assign the TwiML Bin to the Twilio number under **A call comes in**. For local testing:

```bash
uv run bot.py -t twilio -x YOUR_NGROK_HOST
```

See the official [Pipecat Cloud Twilio guide](https://docs.pipecat.ai/pipecat-cloud/guides/telephony/twilio-websocket).
