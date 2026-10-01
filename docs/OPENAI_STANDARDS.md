# OpenAI compatibility and directory status

Checked October 1, 2026. This document describes implemented protocol compatibility. It is not a declaration of OpenAI approval or legal certification.

## Implemented

| Requirement | Implementation / evidence |
|---|---|
| Portable package | Root `plugin.json` and `mcp.json`, Agent Plugins 1.0.0 schema identifiers; OpenAI fields under `extensions.com.openai`. Official schemas validated by `scripts/validate.py`. |
| MCP operations | Individual named tools with explicit input schemas, descriptions, and boolean readOnlyHint/destructiveHint/openWorldHint annotations. Recording and persistent writes are not marked read-only; overwrite/cancellation are marked destructive. |
| Local executable | Bare `sh` command and `${PLUGIN_ROOT}`; no hardcoded developer checkout path. Stable runtime outside the plugin cache. |
| Standard UI | MCP Apps SDK, `ui://` HTML resource, `text/html;profile=mcp-app`, `ui.resourceUri`; no external UI dependencies at runtime. |
| OpenAI surfaces | Official `openai/ui.entrypoints` global/thread metadata on the panel-opening tool. Rendering depends on each host's support. |
| Display modes | Compact inline card has two actions and no tabs/nested navigation. Fullscreen contains the multi-step workspace. Uses the shared bridge to request display mode. |
| Theme/accessibility | Host style variables and native font stack, host light/dark changes, responsive layout, keyboard tab navigation, visible focus, labelled inputs and status/error regions. |
| Network boundary | Empty UI connect/resource domain lists. Audio/model processing is local. No public recorder endpoint or covert cloud audio upload. |
| Optional speaker processing | Explicit setup downloads pinned public model/SDK revisions without account credentials. Inference loads local Core ML files; speaker labels are estimates scoped to the meeting/channel, aliases are user supplied, overlap/uncertainty is retained, embeddings are not persisted. No hidden model download or identity claims. |
| User intent | No auto-recording at launch, calendar selection or installation. Transcripts/event metadata are untrusted data. No automatic chat creation/message routing. |
| Calendar interoperability | Local tools independently accept supplied, validated minimal event metadata. Optional calendar discovery happens in the host workflow; no connector dependency is hidden in tool execution. No bundled app references or Google secrets. |
| Privacy/listing | Publisher, source/support/privacy/terms URLs, icons, example prompts and release metadata. Privacy describes local retention, model-provider text processing and host-based sharing. |
| Packaging | Deterministic source-only ZIP and checksum. No records, credentials, runtime, downloaded models or node_modules. Third-party license notices included. |

## Universal Plugin Directory: outstanding requirements

The current public submission flow requires a verified developer identity. The portal displayed “You need a verified developer identity before you can create or upload a plugin.” Upload was blocked before any draft could be created.

The official package guide also states that public MCP submissions use a remote HTTPS endpoint, and directs local MCP developers to their OpenAI contact for local support. This plugin controls hardware and files on the user's Mac through local stdio. Moving that server to a publisher's machine would not capture the user's microphone. No public tunnel, unauthenticated recorder endpoint or skills-only submission that conceals the local backend is supplied.

A directory submission still needs an accepted local-MCP distribution path (or a separately designed, authenticated companion architecture), verified identity, actual desktop/mobile host validation appropriate to the approved scope, tested review cases, a walkthrough, automated scans and approval. These remain outstanding. The source release and Git marketplace are a supported separate distribution route for local Codex users.

## Primary references

- [Package your plugin](https://developers.openai.com/plugins/build/plugins)
- [MCP server and UI quickstart](https://developers.openai.com/plugins/build/app-quickstart)
- [OpenAI MCP Extensions](https://developers.openai.com/plugins/build/extensions)
- [UI guidelines](https://developers.openai.com/plugins/concepts/ui-guidelines)
- [Plugin guidelines](https://developers.openai.com/plugins/plugin-guidelines)
- [Upload and submit](https://developers.openai.com/plugins/deploy/submission)
