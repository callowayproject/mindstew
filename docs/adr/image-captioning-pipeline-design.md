# Multimodal image captioning pipeline detail

Resolves [Multimodal image captioning pipeline detail](https://github.com/callowayproject/mindstew/issues/20), a child ticket of [Map: Python/macOS native llm_wiki spec](https://github.com/callowayproject/mindstew/issues/1).

Image extraction and captioning is one normalized pipeline stage that runs on the same serial ingest worker as text ingest ([#8](https://github.com/callowayproject/mindstew/issues/8)), just before the two-step CoT step sees the page's Markdown. Every source type funnels through one extraction step; captions are cached per-image (not per-file) and written inline as Markdown alt text; captioning failures degrade gracefully with an independent retry budget; and a manual retry control lives directly on the image in the Preview pane.

## Terms

- **Extraction stage** — the pipeline step that pulls raw images out of a source document (PDF/docx/epub) or reads a standalone image file, before any captioning happens. _Avoid: "parser step."_
- **Captioning stage** — the pipeline step that sends an extracted image to the configured vision-capable LLM and gets back a caption.

## Why

The map's ingest pipeline ([#8](https://github.com/callowayproject/mindstew/issues/8)) and vector-search integration ([#10](https://github.com/callowayproject/mindstew/issues/10)) established how text and embeddings flow through the serial ingest worker, but multimodal image captioning — explicitly in scope per the map's Notes — was left in **Not yet specified**. This ticket pins down where captioning sits in that pipeline, how it's cached, how a caption attaches to a page, how failures are handled, and what UI a user gets to retry or override a bad caption.

Before asking the user, a research subagent checked how upstream [llm_wiki](https://github.com/nashsu/llm_wiki) currently implements this (`src/lib/image-caption-pipeline.ts`), since mindstew is reimplementing most of its feature set. That research directly shaped every recommendation below and is cited inline as "Verified facts."

## Locked decisions

- **Pipeline placement & caching key** ([Q2](#)) — Image captioning is a stage on the *same* serial ingest worker and `ingest.db` used for text ingest and embedding, but it runs **before** the two-step CoT step sees the page's Markdown — so the CoT generation step receives already-captioned image references, not raw ones. It is keyed by **per-image content hash**, not the whole-file SHA256 used for text re-ingest skip logic. Rejected: interleaving captioning into the CoT analysis step itself keyed by whole-file hash (would force re-captioning every image on any unrelated text edit to the source); a fully separate pass/worker with its own scheduling (unnecessary complexity — the existing serial worker already handles staged, cached, resumable work).
- **Caption attachment format** ([Q3](#)) — Captions attach as **inline Markdown alt text** (`![<caption>](path)`) right where the image occurs in the generated page body, plus a supporting record in `ingest.db` keyed by image hash so vector search/chat retrieval ([#10](https://github.com/callowayproject/mindstew/issues/10)) can look up a caption without re-parsing Markdown. Rejected: YAML frontmatter `images` list (captions are body-level prose tied to a specific spot in the page, not page-level metadata — and [#3](https://github.com/callowayproject/mindstew/issues/3) already keeps frontmatter minimal); an `ingest.db`-only record with no trace in the page body (loses the caption from the human-readable page a user opens in Obsidian).
- **Failure handling** ([Q4](#)) — A captioning failure **degrades gracefully with an independent retry-cap-3** per image: the page ingests normally without blocking, the image renders without a caption, and the failure is tracked in its own retry state in `ingest.db` (separate from page-ingest failures) — mirroring [#10](https://github.com/callowayproject/mindstew/issues/10)'s "track separately, don't block the page" convention rather than [#8](https://github.com/callowayproject/mindstew/issues/8)'s page-blocking retry-cap-3. Rejected: matching upstream's fire-and-forget with no retry at all (too soft — many captioning failures are transient rate-limit/network errors worth a retry); blocking the page's ingest until captioning succeeds or exhausts retries (couples a non-core enhancement to core content availability).

## Routine choices

- **Extraction normalization** ([Q1](#)) — One normalized extraction step across all source types: each source-type parser (PyMuPDF for PDF, python-docx for docx, ebooklib for epub) emits a flat list of extracted images with a page/section reference, feeding one shared captioning stage. Standalone image files dropped into `sources/` are the trivial case — read directly, no parsing needed.
- **Model slot & unsupported-provider handling** ([Q5](#)) — Captioning reuses the single configured provider/model (the adapter already covers both text and vision calls per the map's Notes). If the configured provider/transport lacks vision support, mindstew surfaces a visible warning in the Activity dock rather than skipping silently (upstream's behavior) — a separate captioning-specific model slot is out of scope here, deferred to the "Settings/model-routing UI" fog item.
- **Terminal failed-caption surfacing** ([Q6](#)) — A per-image failed-caption entry appears in the Activity dock, mirroring [#8](https://github.com/callowayproject/mindstew/issues/8)'s failed-ingest surfacing. Nothing downstream blocks: the page ingests and gets search-indexed with or without a caption.
- **Image size / cost control** ([Q7](#)) — Extracted images are downscaled before the vision call, with the **max dimension user-configurable** (not a fixed hardcoded default) — the user chose the configurable-setting option over a fixed 1024px default during grilling.
- **Extracted image storage location** ([Q8](#)) — Images land at `wiki/media/<page-slug>/`, alongside the wiki page that references them, matching both the vault layout established in [#2](https://github.com/callowayproject/mindstew/issues/2) and upstream llm_wiki's convention. Markdown image references stay relative and simple, and the media stays visible/browsable in Obsidian (unlike a content-addressed store under `.mindstew/`).
- **Manual caption retry/override UI** ([Q9](#)) — Manual *override* is already free: captions are literal inline Markdown alt text ([Q3](#)), so editing the page's Markdown directly edits the caption, no dedicated editor UI needed. *Retry* gets two triggers: the Activity dock's failed-caption entry (from [Q6](#)) for images that errored out, **and** a right-click "Retry caption" action directly on the image in the Preview pane — covering the more common case of a caption that succeeded but is simply wrong or low-quality, which never appears in the failure list.

## Verified facts

Gathered by a research subagent reading upstream [nashsu/llm_wiki](https://github.com/nashsu/llm_wiki) (README and `src/lib/image-caption-pipeline.ts`), not asked of the user:

- Upstream's README explicitly names only PDF for the captioning feature ("extract embedded images from PDFs, generate factual captions with a vision LLM"); whether docx/epub embedded images flow through the same stage is not confirmed in the source examined. Mindstew's decision (Q1: one normalized step for all source types) goes further than what's confirmed upstream.
- Upstream keys its caption cache as `${imageHash}::language:${encodeURIComponent(language)}` (SHA-256 of image bytes, not the whole file) — directly informed the per-image-hash caching decision (Q2).
- Upstream rewrites `![](path)` to `![<caption>](path)` — directly informed the inline-alt-text decision (Q3).
- Upstream has no retry/backoff for caption failures at all — just logs and moves on, non-blocking per-image. Mindstew's retry-cap-3 (Q4) is intentionally more robust than this.
- Upstream reuses whichever LLM config is passed in, with one explicit exception: captioning is skipped entirely for a transport that doesn't support image input, logged as `"[caption-pipeline] skipped image captioning: ... does not support image input yet."` — directly informed Q5's "reuse the model slot" decision, with mindstew choosing a visible warning over upstream's silent skip.
- The research subagent could not confirm upstream's mechanism for "standalone image sources" ingestion (a recent feature), nor locate the whole-file-hash mechanism used for upstream's text re-ingest skip logic, so no claim is made about how the two caching systems interact upstream.

## Risks

- Per-image content-hash caching (Q2) means the same physical image bytes appearing in two different documents are captioned once and reused — correct for cost, but if a user wants a *context-specific* caption (the same logo captioned differently depending on surrounding content), this design doesn't support that. Not raised as an open question because no signal in the map suggests context-specific captions are a requirement.
- A user-configurable max image dimension (Q7) reopens a small piece of the "Settings/model-routing UI" fog item's territory (a per-project knob) even though that UI's overall shape is still unspecified. The setting itself is locked in scope for this ticket; where it lives in Settings UI remains fog.

## Deferred

None — every branch raised in this session was answered.

## Open threads

None — all discussion threads converged within their question's answer (no threaded discussion sub-branches were opened separately from the answered questions above).
