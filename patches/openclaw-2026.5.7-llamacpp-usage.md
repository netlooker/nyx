# OpenClaw 2026.5.7 llama.cpp Streaming Usage Patch

This is a local runtime workaround for OpenClaw `2026.5.7` when using a
self-hosted llama.cpp OpenAI-compatible endpoint, especially the MTP build used
for `qwen3.6-27b-mtp`.

## Symptom

Fresh OpenClaw sessions show unknown context usage:

```text
Tokens: unknown/262k (?)
```

Session JSONL messages store assistant usage as zeros even though llama.cpp can
return usage when the request includes:

```json
"stream_options": { "include_usage": true }
```

## Preferred Fix

Before reapplying this patch, test the latest OpenClaw release or `main` in a
disposable container. Upstream issue:

<https://github.com/openclaw/openclaw/issues/79897>

If the current release works with only the config change below, do not patch the
bundled runtime.

## Required Config

For trusted RFC1918/LAN llama.cpp endpoints, keep private-network access enabled
on the provider. This belongs in both the active OpenClaw config and the agent
model config if both exist:

- `/config/openclaw.json5`
- `/data/agents/main/agent/models.json`

```json5
models: {
  providers: {
    llamacpp: {
      baseUrl: 'http://<private-lan-ip>:8014/v1',
      api: 'openai-completions',
      apiKey: 'local_inference',
      request: {
        allowPrivateNetwork: true,
      },
      models: [
        {
          id: 'qwen3.6-27b-mtp',
          contextWindow: 262144,
          maxTokens: 32768,
          compat: {
            supportsUsageInStreaming: true,
            supportsDeveloperRole: false,
            supportsStrictMode: false,
            maxTokensField: 'max_tokens',
          },
        },
      ],
    },
  },
}
```

Without `request.allowPrivateNetwork`, OpenClaw's guarded transport can block
the LAN endpoint:

```text
[security] blocked URL fetch (url-fetch) targetOrigin=http://<private-lan-ip>:8014 reason=Blocked hostname or private/internal/special-use IP address
```

## Runtime Patch

Apply only inside the running Nyx container, and only for OpenClaw `2026.5.7`.
These edits are not durable across image rebuilds or OpenClaw reinstalls.

### 1. Route supported OpenAI-compatible APIs through OpenClaw transport

File:

```text
/usr/local/lib/node_modules/openclaw/dist/provider-stream-CdoVdz4F.js
```

Find:

```js
function createTransportAwareStreamFnForModel(model, ctx) {
	if (!hasTransportOverrides(model)) return;
	if (!isTransportAwareApiSupported(model.api)) throw new Error(`Model-provider request.proxy/request.tls is not yet supported for api "${model.api}"`);
	return createSupportedTransportStreamFn(model, ctx);
}
```

Replace with:

```js
function createTransportAwareStreamFnForModel(model, ctx) {
	if (!isTransportAwareApiSupported(model.api)) return;
	return createSupportedTransportStreamFn(model, ctx);
}
```

This makes the local `openai-completions` provider use OpenClaw's transport
path, which sends `stream_options.include_usage=true` and can parse the final
usage chunk.

### 2. Forward final done/error events with usage to message updates

File:

```text
/usr/local/lib/node_modules/openclaw/node_modules/@mariozechner/pi-agent-core/dist/agent-loop.js
```

In `streamAssistantResponse()`, find the `case "done": case "error"` block.
The patched block should copy usage from the raw stream event onto the final
message and emit the terminal event as a `message_update` before `message_end`:

```js
case "done":
case "error": {
    const finalMessage = await response.result();
    if (event.message?.usage && finalMessage && typeof finalMessage === "object") {
        finalMessage.usage = event.message.usage;
    }
    if (addedPartial) {
        context.messages[context.messages.length - 1] = finalMessage;
    }
    else {
        context.messages.push(finalMessage);
    }
    if (!addedPartial) {
        await emit({ type: "message_start", message: { ...finalMessage } });
    }
    await emit({
        type: "message_update",
        assistantMessageEvent: event,
        message: { ...finalMessage },
    });
    await emit({ type: "message_end", message: finalMessage });
    return finalMessage;
}
```

## Restart

```bash
docker compose -f container/docker-compose.yml restart nyx
```

## Verification

Run a fresh session. Existing sessions that already persisted zero usage will
remain unknown.

```bash
docker compose -f container/docker-compose.yml exec nyx \
  sh -lc 'openclaw tui --session usage-probe --timeout-ms 90000 --deliver --message "/no_think Reply with exactly: usage ok"'
```

Then check status:

```bash
docker compose -f container/docker-compose.yml exec -T nyx openclaw status
```

Expected result for the fresh probe is a concrete token count, for example:

```text
51k/262k (19%) · 81% cached
```

If the fresh session still shows `unknown/262k (?)`, inspect:

```bash
docker compose -f container/docker-compose.yml logs --since=5m nyx
```

Look for blocked private-network fetches, zero assistant usage, or failed model
requests.

