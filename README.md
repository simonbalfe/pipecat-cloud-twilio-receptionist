# Pipecat Cloud Twilio Receptionist Template

A small, fully code-managed Python voice agent for Pipecat Cloud and Twilio. Fork it,
configure `.env`, then run one command to deploy the agent and connect the number. See
[Architecture](docs/architecture.md) for the complete system in one diagram.

## Included workflow

1. During configured business hours, redirect the Twilio call to `OWNER_PHONE`.
2. Outside business hours, ask whether the caller is a surveyor.
3. Surveyors leave a message, which is emailed to `EMAIL_TO`.
4. Other callers provide the property type, required service, address, and confirmed postcode; the enquiry is emailed to `EMAIL_TO`.
5. If the owner redirect request fails, fall back to the AI flow.

The workflow is ordinary Python in `receptionist/`. There is no visual workflow state.

## Accounts

- Pipecat Cloud
- Twilio Programmable Voice number
- Deepgram for speech-to-text and text-to-speech
- OpenRouter for the language model
- Cloudflare Email Service with an onboarded sending domain

## One-shot setup

```bash
cp .env.example .env
${EDITOR:-nano} .env
./setup
```

The setup validates the configuration and Twilio number before changing anything. It then:

1. uploads only the runtime secrets to Pipecat Cloud;
2. builds and deploys `PIPECAT_AGENT_NAME` in `PIPECAT_ORGANIZATION`;
3. removes the selected number from an old SIP trunk, if necessary;
4. configures the number to stream calls to the deployed agent.

It never writes credentials to tracked files. Running `./setup` again updates the existing
deployment and route.

The Cloudflare token needs `Email Sending Write` for `CLOUDFLARE_ACCOUNT_ID`.
`EMAIL_FROM` must use an onboarded sending domain; verify `EMAIL_TO` in Cloudflare to send
notifications free on any Workers plan.

## Check

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run python -m unittest discover -s tests
```

With `min_agents = 0`, the service scales to zero between calls.
Set `PIPECAT_MIN_AGENTS=1` to remove the roughly 9-second platform cold start; this keeps
one agent running and adds idle hosting cost. Warm conversational turns use an 800 ms
maximum stop wait plus bounded, low-temperature LLM responses.

For local testing:

```bash
uv run bot.py -t twilio -x YOUR_NGROK_HOST
```

See the official [Pipecat Cloud Twilio guide](https://docs.pipecat.ai/pipecat-cloud/guides/telephony/twilio-websocket).
