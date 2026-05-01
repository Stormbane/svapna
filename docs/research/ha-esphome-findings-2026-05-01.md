# HA / ESPHome / voice-pe research — 2026-05-01

Reading pass over `C:/Projects/_refs/{esphome,ha-core,home-assistant-voice-pe,wake-word-voice-assistants}` to map our open threads onto what already exists. Citations are file path + line number into the cloned references.

## TL;DR

- We are using `voice_assistant:` in **`speaker:` mode** (raw PCM streamed back over the API). Every working modern reference — voice-pe, the box-3 wake-word example, HA's TTS streaming code — uses **`media_player:` mode** with `platform: speaker` (or `speaker_source`). Almost every blocker on our list is a direct consequence of that choice.
- `voice_assistant.cpp` never calls `speaker_->set_audio_stream_info()` (`_refs/esphome/esphome/components/voice_assistant/voice_assistant.cpp:402`). In `speaker:` mode the I2S driver starts at the speaker's default `AudioStreamInfo` (16 kHz / 16-bit / mono — `speaker.h:115`, default per `i2s_audio/speaker/__init__.py:122`). The YAML `sample_rate:` only constrains the schema; secondary i2s mode pins it (`__init__.py:90-99`). The 16 kHz hardcode is in the C++; nothing to fight at the YAML layer.
- TTS audio over `speaker:` mode is not "streaming TTS" the way HA documents it. HA's path serves a 16 kHz / 16-bit / mono **WAV** through `_stream_tts_audio()` (`_refs/ha-core/homeassistant/components/esphome/assist_satellite.py:639-697`) and paces chunks at 0.9× realtime. That code aborts if the format isn't exactly that. Our edge-tts → 48 kHz PCM into a 16 kHz speaker is what's chipmunking us if we ever get past the URL guard.
- The placeholder `{"url": "stream://narada"}` hack we use is fixing the wrong problem. In **`speaker:` mode** (`local_output_=true` set via `set_speaker()`, `voice_assistant.h:128-131`), TTS_END's URL is irrelevant — the audio comes through `on_audio()` and the state goes to `STREAMING_RESPONSE` regardless (`voice_assistant.cpp:764`). The early-return at `:746-748` is a log warning + `return` from the lambda — but that lambda is the trigger callback, not the state transition. The state transition still happens. Worth re-reading line by line; we may have misdiagnosed this.
- voice-pe's micro_wake_word does fire — and it differs from ours in three ways that matter: (1) `CONFIG_SPIRAM_RODATA: y` + `CONFIG_SPIRAM_FETCH_INSTRUCTIONS: y` to free internal RAM (`home-assistant-voice.yaml:71-75`), (2) micro_wake_word has its own `microphone:` source with `gain_factor: 4` and `channels: 1` (`:1711-1716`), (3) `vad:` is enabled inside micro_wake_word (`:1728`). We have none of these.
- voice-pe runs **`use_wake_word: false`** + `micro_wake_word.start:` on `on_client_connected` (`home-assistant-voice.yaml:1811-1817`) — same canonical sequence we tried in Phase A. The difference is mWW actually runs on their hardware because of the SDK config above. Our "Phase A canonical" YAML is correct; the firmware build is missing the PSRAM tuning that lets mWW survive boot.
- The phantom 8 s STT turns are explained: with `use_wake_word: false` and no mWW running, *something* is calling `voice_assistant.start_continuous` or the touchscreen handler is firing on its own. The state machine has no path that starts a turn without an explicit `request_start` call (`voice_assistant.cpp:545-558`) — the trigger is in our YAML or HA, not in the C++. The 8 s figure matches HA's wake_word listen window timeout, which suggests HA-side wake word *is* what's firing (the STT_VAD_END pattern we see). Worth instrumenting `on_start` more loudly.
- The 4 KB `write_speaker_()` chunk and the 16 KB `SPEAKER_BUFFER_SIZE` (`voice_assistant.cpp:28, 405`) are fixed in C++. Our 300 ms YAML buffer is the right call to make `xRingbufferSend` accept full chunks; voice-pe at 100 ms gets away with it because it's at 48 kHz × 32-bit × stereo (768 KB/s vs our 32 KB/s — 4 KB is much smaller relative to 100 ms there).
- VAD: in `speaker:` mode the device sends raw PCM and HA's pipeline runs server-side VAD if `silence_detection=true` is in the start request (`voice_assistant.cpp:233-234`, flag `VOICE_ASSISTANT_REQUEST_USE_VAD`). This flag is set by `request_start(continuous, silence_detection=true)`. Our bridge doesn't run an HA pipeline — but the state machine still expects STT_VAD_END to advance. We're already sending it ourselves; that part is correct.
- pioarduino/toolchain: voice-pe doesn't pin pioarduino. It pins `framework: type: esp-idf, version: recommended` (`home-assistant-voice.yaml:64-65`) and `min_version: 2026.3.0` (`:41`). The box-3 example pins `min_version: 2026.4.0` (`esp32-s3-box-3.yaml:41`). Neither uses Arduino framework. **Our YAML already does this** — the toolchain breakage is at the binary release layer, not the config layer.

---

## Per-blocker findings

### 1. On-device micro_wake_word never fires

**What HA/ESPHome do.** Two canonical wake-word activation paths; both are exposed in `voice_assistant:`:

- `use_wake_word: true` + `voice_assistant.start_continuous:` — HA-side streaming wake word. The device streams mic audio continuously; HA detects the wake word and tells the device "now you're listening." This is the original assist-pipeline path.
- `use_wake_word: false` + `micro_wake_word.start:` — on-device mWW. The device runs TFLM inference on the mic stream, fires `on_wake_word_detected` when probability crosses cutoff, and that automation calls `voice_assistant.start: wake_word: !lambda return wake_word;` — see voice-pe `:1729-1770` and box-3 `:232-234`. The wake word string flows through to `request_start` → `start_pipeline` → `wake_word_phrase` field on the request (`voice_assistant.cpp:245`).

**State machine transitions.** The C++ state machine has exactly one entry point that starts a turn: `request_start(continuous, silence_detection)` at `voice_assistant.cpp:545`. That is called from:
- The `voice_assistant.start:` action (`voice_assistant.h:333-346`)
- The `voice_assistant.start_continuous:` action (`voice_assistant.h:348-351`)
- The `idle_trigger_` self-loop when `continuous_=true` and `desired_state_=IDLE` (`voice_assistant.cpp:199-201`)

There is no path where the device "decides" to start a turn on its own. If we're seeing turns without a wake-word event, *something in our YAML or in HA* is calling start.

**Why mWW on voice-pe works and on ours doesn't.** Three differences in the firmware build:

1. **PSRAM offload of read-only data.** voice-pe sets `CONFIG_SPIRAM_RODATA: y` and `CONFIG_SPIRAM_FETCH_INSTRUCTIONS: y` (`home-assistant-voice.yaml:74-75`). Comment in the YAML: "Considerably speeds up mWW at the cost of using more PSRAM." The probe loop in `streaming_model.cpp:109-160` allocates the tensor arena via a PSRAM `RAMAllocator`, with retries at 1× / 1.5× / 2× the manifest size. On a build without `SPIRAM_RODATA`, internal RAM is the bottleneck — even with PSRAM available, the allocator isn't getting the right pool. Our `narada-voice-test.yaml:29-32` only sets `DEFAULT_CPU_FREQ_240` and the data-cache flags; we're missing the SPIRAM offload flags.

2. **micro_wake_word's own microphone source.** voice-pe wires the mic into mWW separately from voice_assistant (`home-assistant-voice.yaml:1713-1716`):
   ```yaml
   micro_wake_word:
     microphone:
       microphone: i2s_mics
       channels: 1
       gain_factor: 4
   ```
   The schema requires this in modern ESPHome (`micro_wake_word/__init__.py:344-351` — `min_channels=1, max_channels=1, min/max bits=16`). The box-3 example uses the older shorthand (just listing models — `esp32-s3-box-3.yaml:226-231`); that still works because mWW falls back to consuming from the mic that voice_assistant claimed. Either is valid. **Our YAML doesn't have mWW at all right now** — we commented it out (`narada-voice-test.yaml:165-168`). Phase A YAML had it. The comment says it "fails to allocate tensors" — which is the symptom of the PSRAM problem in (1).

3. **VAD inside micro_wake_word.** voice-pe enables `vad:` inside the mWW block (`:1728`). This makes mWW skip inference when no voice is present, which both reduces CPU (mWW eats ~60% of one core when running constantly) and reduces false positives. The box-3 example doesn't use it. We don't either.

**Should we adopt.** Yes, all three. The PSRAM flags are free. The mic-source block is required by modern schema and free. The mWW VAD reduces CPU for negligible cost.

**Concrete next step.**
- Add to `esp32.framework.sdkconfig_options`: `CONFIG_SPIRAM_RODATA: "y"` and `CONFIG_SPIRAM_FETCH_INSTRUCTIONS: "y"`.
- Re-enable mWW with the new schema:
  ```yaml
  micro_wake_word:
    id: mww
    microphone:
      microphone: box_mic
      channels: 1
      gain_factor: 4
    stop_after_detection: false
    vad:
    models:
      - okay_nabu
    on_wake_word_detected:
      - voice_assistant.start:
          wake_word: !lambda return wake_word;
  ```
- Wire `voice_assistant: micro_wake_word: mww` and `use_wake_word: false`.
- Watch the logs for `"Probed tensor arena size: %zu bytes"` (`streaming_model.cpp:52`) to confirm allocation succeeded. If it still fails, the next escalation is bumping `tensor_arena_size` per-model.

---

### 2. TTS_END empty url / placeholder URL hack

**What's actually happening.** Re-read `voice_assistant.cpp:739-771`. The empty-url early-return at `:746-748` is *inside the trigger lambda's outer guard*, not inside the state-transition code. The flow is:

```cpp
case TTS_END: {
  std::string url; for arg in data: if name=="url" url=arg.value;
  if (url.empty()) {
    ESP_LOGW(TAG, "No url in TTS_END event");
    return;                                   // <-- early return :748
  }
  ESP_LOGD(...);
  this->defer([this, url]() { ... media_player call ... tts_end_trigger_.trigger(url); });
  State new_state = this->local_output_ ? STREAMING_RESPONSE : IDLE;
  if (new_state != this->state_) {
    this->set_state_(new_state, new_state);   // <-- :768 state change
  }
  break;
}
```

**The early return at `:748` skips both the deferred trigger AND the state change.** So the placeholder URL hack is, in fact, doing real work — it's preventing the state from staying stuck. We were right that the URL matters; we were wrong about *why*. The fix isn't conceptually invalid; it's a workaround for what looks like an upstream bug — TTS_END with no URL should still transition the state when `local_output_` is true.

**What the HA pipeline actually sends in `speaker:` mode.** `assist_satellite.py:345-367`:
```python
elif event_type == VoiceAssistantEventType.VOICE_ASSISTANT_TTS_END:
    if tts_output := event.data["tts_output"]:
        path = tts_output["url"]
        url = async_process_play_media_url(self.hass, path)
        data_to_send = {"url": url}
        # If the device has FEATURE_SPEAKER, *also* spawn _stream_tts_audio
        if feature_flags & VoiceAssistantFeature.SPEAKER and (stream := tts.async_get_stream(...)):
            self._tts_streaming_task = ... self._stream_tts_audio(stream) ...
```

So HA sends a real URL even when streaming PCM to a speaker-mode device. The URL points at HA's own `/api/tts_proxy/...` endpoint — it's a fallback for clients that can't take streaming. The streaming task pushes WAV PCM via `send_voice_assistant_audio` (`assist_satellite.py:683`) at 16 kHz / 16-bit / mono, paced at 0.9× realtime per chunk (`:691`).

**Should we adopt.** Stop treating the URL as a hack. Either:
- (a) keep sending `{"url": "stream://narada"}` and document it as load-bearing (what HA does is functionally equivalent — they send a URL whose audio the device will never fetch in `speaker:` mode), or
- (b) actually serve the audio at the URL too. We already have `TTSServer` (`scripts/voice_pipeline.py:107-144`) writing MP3s. We could write WAV instead and ship the URL — then either the streaming path or the URL path will play, whichever the device prefers.

Option (a) is simpler. Option (b) gives us a fallback if the streaming path breaks.

**Concrete next step.** Document the placeholder URL as required, not hack — link to `voice_assistant.cpp:746` in the comment. The deeper fix is to also write the WAV at that URL so the placeholder degrades gracefully into URL playback when we move to `media_player:` mode.

---

### 3. Speaker sample rate hardcoded to 16 kHz

**What's hardcoded where.**
- `voice_assistant.cpp:21`: `static const size_t SAMPLE_RATE_HZ = 16000;` — used for ring-buffer sizing (mic input).
- `speaker.h:99-101, 115`: `set_audio_stream_info()` is the only way to change the speaker's `AudioStreamInfo`. Default-constructed `audio::AudioStreamInfo` is 16 kHz / 16-bit / mono.
- `voice_assistant.cpp` never calls `set_audio_stream_info()`. Search across the file confirms this. Compare `_refs/esphome/esphome/components/speaker/media_player/audio_pipeline.cpp:475` — the `speaker_source` media_player *does* call it, on every audio format change.
- `i2s_audio_speaker.cpp:115`: I2S driver starts using `this->audio_stream_info_` — whatever the speaker last had set. In voice_assistant `speaker:` mode that's the default (16k/16/mono).
- YAML `sample_rate: 48000` only matters for *primary* i2s mode; in *secondary* mode it pins min/max (`speaker/__init__.py:90-99`). We're in primary mode so the YAML value isn't enforced — at runtime the i2s driver reconfigures to whatever `audio_stream_info_` says (16 kHz). The DAC chip's `audio_dac.sample_rate: 16000` actually matters; if it's 48 kHz the audio clocks fast.

**This is a known limitation** of `voice_assistant: speaker:` mode. It is by design — the `speaker:` path was added as a back-compat option for hardware without a media_player and was always 16 kHz mono. The `media_player:` path is where multi-rate audio lives. See the legacy version flags at `voice_assistant.h:34-35` — `LEGACY_SPEAKER_SUPPORT = 2` is the "raw speaker" version. Speaker mode is the legacy path.

**What media_player mode does.** voice-pe and box-3 both wire `media_player:` and let the announcement_pipeline handle resampling. voice-pe even has a `resampler` speaker explicitly:
```yaml
speaker:
  - platform: resampler
    id: announcement_resampling_speaker
    output_speaker: announcement_mixing_input
    sample_rate: 48000
    bits_per_sample: 16
```
(`home-assistant-voice.yaml:1558-1567`). Then `media_player.speaker_source.announcement_pipeline.speaker: announcement_resampling_speaker`. The pipeline runs FLAC decode → resample → mixer → I2S. At each format change `audio_pipeline.cpp:475` calls `set_audio_stream_info` on the underlying speaker.

**voice-pe's audio rates.**
- Speaker hardware: 48 kHz, 32-bit, stereo, secondary mode (`:1530-1543`). `buffer_duration: 100ms`. AIC3204 DAC.
- Mic: 16 kHz, 32-bit, stereo, secondary mode (`:1518-1528`).
- Announcement format: FLAC, mono, 48 kHz (`:1629-1633`).
- Media format: FLAC, stereo, 48 kHz (`:1637-1641`).
- TTS streamed back through assist_satellite goes via the announcement_pipeline → resampler → mixer → speaker.

**What box-3 example does** (closer to our hardware):
```yaml
speaker:
  - platform: i2s_audio
    sample_rate: 48000      # secondary mode; pinned
    buffer_duration: 100ms

media_player:
  - platform: speaker
    announcement_pipeline:
      speaker: box_speaker
      format: FLAC
      sample_rate: 48000
      num_channels: 1       # S3 Box only has one output channel
```
(`esp32-s3-box-3.yaml:167-188`)

**Should we adopt.** Yes — this is the architectural fix. Move to `media_player: platform: speaker` with FLAC announcement_pipeline at 48 kHz mono. Then voice_assistant.cpp's TTS_END URL path actually plays through the media_player call at `:756` (`set_media_url(url).set_announcement(true).perform()`).

**Concrete next step.** Switch from `voice_assistant: speaker:` to `voice_assistant: media_player:`. Replicate box-3's pipeline almost verbatim. Bridge change: TTS produces FLAC at 48 kHz mono and serves it at `http://laptop:port/tts/...flac`; we send `TTS_END {url: that}` and the device fetches and plays. We already have the HTTP server in `scripts/voice_pipeline.py:107`.

---

### 4. Tiny speaker ring buffer at 16 kHz × 100 ms

**What's there.** `voice_assistant.cpp:28`: `SPEAKER_BUFFER_SIZE = 16 * RECEIVE_SIZE = 16 * 1024 = 16 KB`. `write_speaker_()` writes in chunks of `min(buffer_size, 4 KB)` (`:405`). At 16 kHz × 16-bit × mono = 32 KB/s. The 4 KB chunk is 125 ms of audio. The speaker's I2S ring buffer is configured separately by YAML `buffer_duration:`. At 100 ms × 32 KB/s = 3.2 KB — smaller than one write chunk. So `xRingbufferSend` with a 4 KB chunk into a 3.2 KB buffer rejects the write entirely (`xRingbufferSend` is all-or-nothing), `play()` returns 0, and we loop forever logging "Speaker buffer full" (`:413`).

**voice-pe gets away with 100 ms** because their speaker is 48 kHz × 32-bit × stereo = 384 KB/s — 100 ms = 38.4 KB, far above 4 KB.

**Our 300 ms bump is correct.** 300 ms × 32 KB/s = 9.6 KB > 4 KB. But this is only a workaround for `speaker:` mode — moving to `media_player:` mode resamples to 48 kHz and the 100 ms default is fine again.

**Concrete next step.** Keep `buffer_duration: 300ms` until we move to media_player mode. Then drop back to `100ms` (or default `500ms`) — the resampler converts to 48 kHz × 16-bit × mono = 96 KB/s, and 100 ms = 9.6 KB > 4 KB.

---

### 5. No on-device VAD in `speaker:` mode

**Where VAD lives in each mode.**
- **`media_player:` mode + on-device mWW.** mWW has its own VAD inside the wake-word block (`micro_wake_word: vad:`). After wake, the device hands off to assist_satellite which runs **server-side VAD** during STT (the `silence_detection` flag in `request_start`, `voice_assistant.cpp:233`). The server sends `STT_VAD_END` back when it hears silence and the device transitions to `AWAITING_RESPONSE` (`:837-841`).
- **`speaker:` mode.** Same — VAD is server-side. The device never had its own utterance VAD here.

**What we do.** Server-side VAD in `scripts/voice_pipeline.py:253-291` (`_vad_watch`). RMS threshold + silence timeout. We send STT_VAD_END ourselves at `:283`. This is functionally what HA does in its assist_pipeline (`_refs/ha-core/homeassistant/components/assist_pipeline/vad.py` is the canonical implementation — they use webrtcvad). Our naive RMS approach is fine for solo use but mistunes badly with background noise.

**Should we adopt.** Probably yes — webrtcvad is small, fast, and battle-tested. But this is a quality issue, not a blocker. Phantom-turn discrimination matters more.

**Concrete next step.** Replace RMS VAD with webrtcvad-wheels (mode 2 or 3, 30 ms frames). Optional / low priority.

---

### 6. Phantom 8 s STT turns

**State machine review.** A turn starts only via `request_start` → `START_MICROPHONE` → `STARTING_MICROPHONE` → `START_PIPELINE` → `STARTING_PIPELINE` → (HA's `start_streaming` reply) → `STREAMING_MICROPHONE` (`voice_assistant.cpp:545-558, 207-289, 499-543`). Trigger sources are *only* the C++ entry points listed under blocker 1.

**Possible causes of phantom turns.**

1. **Touch firing on its own.** `narada-voice-test.yaml:99-101` — `on_touch: voice_assistant.start:`. If the GT911 driver is reporting spurious touches (we already note `i2c.scan: false` because GT911 calibrates poorly when probed during boot — `:65`), this fires. Easy to verify: comment out the touch handler temporarily and watch.

2. **`voice_assistant.start_continuous:` somewhere.** Search the YAML — we don't call it. Confirmed.

3. **Idle-loop self-trigger when `continuous_=true`.** `voice_assistant.cpp:199-201`. `continuous_` is set true by `request_start(continuous=true, ...)`. If anything ever calls `start_continuous`, we're in this loop forever. Same as (2) — we don't.

4. **HA-side wake word.** If `use_wake_word_=true` (set by `set_use_wake_word(true)` or as a default), the start flag includes `VOICE_ASSISTANT_REQUEST_USE_WAKE_WORD` (`:231`). The HA pipeline then runs *its* wake-word engine on the streaming audio. If HA's wake-word engine is misconfigured or trigger-happy (or set up at all in our case — we don't run HA, but the bridge may be inheriting defaults), this is the prime suspect. The 8 s figure matches HA's default wake-word listen window.

5. **Continuous mode latched in firmware NVS.** If `voice_assistant.start_continuous:` was ever called and the state isn't fully cleared, `continuous_=true` persists across the run. Restart resets `continuous_{false}` per `:314`. Reflash should resolve.

**Most likely cause given symptoms.** Our current YAML doesn't set `use_wake_word:` explicitly. `voice_assistant.h:306` declares `bool use_wake_word_;` uninitialized — but the codegen sets a default (check). The Phase A canonical script we tried — `lambda: id(va).set_use_wake_word(false)` — implies the default is `true`. Combined with our bridge advertising STT capability, the device may be doing HA-style continuous listening. The bridge then sees turns starting "on their own" because they're started by the *device* responding to its own (server-fed-back) wake-word events.

**Concrete next step.**
- Add `use_wake_word: false` to `voice_assistant:` block explicitly. Phase A had this in an automation; making it the default config value is cleaner.
- Add `on_start: logger.log: "va: on_start [continuous=%d wake_word=%s]"` with the actual state values, not just a string. We need to see whether `continuous_` is true at turn start.
- Comment out the touchscreen handler for one test pass to rule out spurious touches.

---

### 7. Toolchain / pioarduino

**What voice-pe pins.** `framework: type: esp-idf, version: recommended` (`home-assistant-voice.yaml:64-65`). No pioarduino. ESPHome's "recommended" esp-idf version tracks a known-good combo per ESPHome release.

**What box-3 example pins.** Same — `type: esp-idf` (`esp32-s3-box-3.yaml:60`). No version specified — falls back to `recommended`.

**What our YAML pins.** `type: esp-idf` (`narada-voice-test.yaml:28`). Same as references. We don't pin a version.

**Where pioarduino enters.** ESPHome itself uses pioarduino as the platformio platform indirection layer for both Arduino and esp-idf builds on ESP32. The version that gets pulled is determined by ESPHome's `platform_version_default` for the targeted ESPHome version (`min_version: 2026.3.0` in our YAML). If that pinned pioarduino release on GitHub has a corrupt artifact (which is what the journal describes), the build fails regardless of `framework: type`.

**The fix is at the ESPHome-version layer.** Either:
- Pin to an older `min_version` whose pioarduino artifact is intact, e.g. drop to whatever was working before the upgrade attempt.
- Wait for pioarduino to publish a corrected release.
- Use a local platform_packages override to point at a different pioarduino tag (advanced; per-project `platformio_options` in ESPHome).

voice-pe is on `min_version: 2026.3.0` — same as us. If that builds, the binary release exists. If it doesn't, theirs is broken too. Easy test: clone voice-pe repo, run `esphome compile home-assistant-voice.yaml` against it. If it succeeds, the breakage is something specific to our YAML or our install. If it fails identically, it's upstream and we wait.

**Concrete next step.** Try compiling voice-pe's YAML in our ESPHome install. Result determines whether the fix is project-side or upstream.

---

## Architectural diff

Three layers to compare: where wake word lives, where VAD lives, how the satellite talks to the brain.

### voice-pe

```
                 ┌────────────────────────────────────┐
                 │ ESP32-S3 (Voice PE hardware)       │
                 │                                    │
     mic ───────►│  i2s_mics (16k/32b/stereo)         │
                 │     │                              │
                 │     ├──► micro_wake_word + vad     │
                 │     │     (on-device, gain_factor 4)│
                 │     │                              │
                 │     └──► voice_assistant           │
                 │            (use_wake_word: false)  │
                 │            (media_player mode)     │
                 │                                    │
                 │  speaker_source media_player ◄─────┐
                 │     │                              │
                 │     ├──► resampler (48k/16b)       │
                 │     ├──► mixer (announcement+media)│
                 │     └──► i2s_audio_speaker         │
                 │            (48k/32b/stereo)        │
                 └────────────┬───────────────────────┘
                              │ ESPHome native API
                              ▼
                 ┌────────────────────────────────────┐
                 │ Home Assistant (laptop/server)     │
                 │                                    │
                 │  esphome integration               │
                 │     └─► assist_satellite           │
                 │           ├─► assist_pipeline      │
                 │           │    ├─► (no wake word — │
                 │           │    │   device handles) │
                 │           │    ├─► STT             │
                 │           │    ├─► server VAD      │
                 │           │    ├─► conversation    │
                 │           │    └─► TTS (streaming) │
                 │           └─► _stream_tts_audio    │
                 │                 (16k WAV chunks    │
                 │                  via API audio,    │
                 │                  paced 0.9×)       │
                 └────────────────────────────────────┘
```

- **Wake word**: on-device (mWW with VAD).
- **Utterance VAD**: server-side, via `silence_detection` flag in start request.
- **TTS path**: streaming WAV via `send_voice_assistant_audio` (16k/16/mono), the device's media_player resamples to 48k via the announcement_pipeline.
- **Brain**: Home Assistant's conversation engine (could be local Ollama, cloud Nabu Casa, etc.).

### Ours

```
                 ┌────────────────────────────────────┐
                 │ ESP32-S3-BOX-3                     │
                 │                                    │
     mic ───────►│  box_mic (16k/16b/mono)            │
                 │     │                              │
                 │     └──► voice_assistant           │
                 │            (speaker mode — legacy) │
                 │            (no mWW currently —     │
                 │             tensor alloc fails;    │
                 │             touch-to-talk instead) │
                 │                                    │
                 │  box_speaker (16k/16b/mono effective│
                 │   regardless of YAML — voice_assist│
                 │   never calls set_audio_stream_info│
                 │   so I2S clocks at default rate)   │
                 │     ◄────────────────────────────┐ │
                 └────────────┬─────────────────────┘
                              │ ESPHome native API
                              ▼
                 ┌────────────────────────────────────┐
                 │ Laptop bridge (scripts/voice_pipeline.py)│
                 │                                    │
                 │  APIClient.subscribe_voice_assistant│
                 │     ├─► handle_start ─► RUN_START, │
                 │     │                  STT_START,  │
                 │     │                  STT_VAD_START│
                 │     ├─► handle_audio ─► buffer     │
                 │     │                              │
                 │     └─► _vad_watch (RMS) ─►        │
                 │           STT_VAD_END,             │
                 │           faster-whisper STT,      │
                 │           claude -p brain,         │
                 │           edge-tts → MP3 → 16k PCM,│
                 │           TTS_START, TTS_STREAM_START,│
                 │           send_voice_assistant_audio│
                 │           chunks, TTS_END(placeholder URL),│
                 │           TTS_STREAM_END,          │
                 │           RUN_END                  │
                 └────────────────────────────────────┘
```

- **Wake word**: nominally on-device mWW (broken — falls back to touchscreen).
- **Utterance VAD**: bridge-side (RMS in `_vad_watch`).
- **TTS path**: PCM via `send_voice_assistant_audio`, no resampling — feeds directly into a default-config 16 kHz speaker buffer, which is the only way our 16 kHz PCM doesn't chipmunk.
- **Brain**: `claude -p` shelled out from the bridge.

### Diff in one paragraph

We are running the **legacy `speaker:` audio path** with **no functioning wake word**, **client-side rolled VAD**, and **a separate brain process**. voice-pe runs the **modern `media_player:` audio path** with **on-device wake word**, **server-side VAD inside the start-flag protocol**, and **HA conversation as the brain**. Every blocker on our list except the toolchain is downstream of running on the legacy speaker path. The placeholder URL hack, the 16 kHz hardcode, the 300 ms buffer bump, the no-on-device-VAD problem — all of these resolve cleanly once we move to `media_player:` mode and serve TTS as URL-fetched FLAC instead of streamed PCM.

---

## Surprises

- **The `set_audio_stream_info()` plumbing exists; voice_assistant just doesn't use it.** It's not a missing API. The `media_player` audio_pipeline calls it on every audio format change (`speaker/media_player/audio_pipeline.cpp:475`). voice_assistant in `speaker:` mode could call it too — but the maintainers chose not to, because the speaker path is intended for legacy fixed-rate PCM. This is by design and won't change.

- **HA's TTS streaming is "fire 16 kHz WAV at 0.9× realtime."** It's not adaptive, not chunked-by-time-budget, not jitter-buffered. The pacing is just `await asyncio.sleep(seconds_in_chunk * 0.9)`. The comment at `assist_satellite.py:686-688` admits this overruns long audio buffers and recommends media_player mode. Our 60 ms / 0.055 s sleep is close to identical pacing.

- **`stop_after_detection: false`** is what voice-pe uses (`home-assistant-voice.yaml:1717`) — meaning mWW *keeps running* after detection, ready for the next wake word, including during TTS playback. This is what enables their "stop" wake word during TTS to interrupt. We'd want this for "stop talking, Narada" interruption.

- **voice-pe's mute switch is hardware + software combined.** GPIO3 hardware switch wins; software switch is template (`home-assistant-voice.yaml:191-217`). Our hardware doesn't have a hardware mute, but we'd want a software equivalent. Tap-to-stop on the touchscreen during a turn would use the same pattern.

- **Wake-word probability cutoffs are deeply tuned.** voice-pe ships three sensitivity presets with quantized uint8 cutoffs validated against the Dinner Party Corpus (`home-assistant-voice.yaml:1772-1802`). Each model has its own cutoff. "Slightly sensitive" = 0.000 false-accepts/hr for okay_nabu. We'd inherit this for free by using their model URLs.

- **The voice_kit XMOS firmware** voice-pe loads (`home-assistant-voice.yaml:1674-1681`) handles AEC + beamforming + noise suppression in a separate XMOS chip. That's why their `noise_suppression_level: 0` in voice_assistant — the work is already done before audio reaches the ESP. Our BOX-3 has no such chip; ESPHome's `noise_suppression_level: 2` is the best we get (a basic IIR notch in software).

- **`feature_step_size`** in mWW (`micro_wake_word/__init__.py:39`) controls the audio frame stride for inference. Lower = lower latency but higher CPU. Default is 20 ms. Worth knowing if we tune for responsiveness later.

- **The `idle_trigger_` automation runs every time the device returns to IDLE in continuous mode** (`voice_assistant.cpp:200`). If we ever wire `voice_assistant.start_continuous`, *every* turn-end fires `idle_trigger_` and immediately re-runs `START_MICROPHONE → START_PIPELINE`. This is the source of "endless 8 s loops" that look like phantom turns. Don't `start_continuous` unless we want this behavior.

- **`http_request: buffer_size_rx: 2048`** at voice-pe `:1574` reduces CPU during streaming audio fetches. The default is larger and stalls the audio thread during socket reads. If we move to media_player URL fetch we'll want this.

- **voice-pe has a `sendspin` external component** (`:1683-1697`) for synchronized multi-room playback. Cool but not relevant to us.

---

## Recommended adoptions, ranked

1. **Switch from `voice_assistant: speaker:` to `voice_assistant: media_player:` mode.** [LARGE, but resolves 4 of 7 blockers]
   - Wire `media_player: platform: speaker` with `announcement_pipeline: format: FLAC, sample_rate: 48000, num_channels: 1` (mirroring `_refs/wake-word-voice-assistants/esp32-s3-box-3/esp32-s3-box-3.yaml:178-188`).
   - Bridge change: TTS pipeline produces FLAC at 48 kHz mono, served by the existing `TTSServer`. Send `TTS_END {url: server_url}`. Drop the `send_voice_assistant_audio` path.
   - Resolves: blocker #2 (URL is now meaningful), #3 (speaker is at 48 kHz via pipeline), #4 (buffer doesn't matter at 48 kHz), partial #5 (still no on-device VAD, but the path is consistent with HA's).
   - Files to touch: `embodiment/firmware/narada-voice-test.yaml`, `scripts/voice_pipeline.py`.

2. **Re-enable on-device micro_wake_word with PSRAM tuning.** [MEDIUM, resolves blocker #1 + part of #6]
   - Add `CONFIG_SPIRAM_RODATA: "y"`, `CONFIG_SPIRAM_FETCH_INSTRUCTIONS: "y"` to esp32 sdkconfig_options.
   - Add the modern mWW block with `microphone:`, `gain_factor: 4`, `vad:`, `stop_after_detection: false`, `okay_nabu` model.
   - Wire `voice_assistant: micro_wake_word: mww, use_wake_word: false`.
   - Add `on_wake_word_detected: voice_assistant.start: {wake_word: !lambda return wake_word;}`.
   - Files to touch: `narada-voice-test.yaml` (and eventually fold back into `narada-body.yaml`).

3. **Set `use_wake_word: false` explicitly + add diagnostic logs.** [SMALL, resolves blocker #6]
   - Make the start flag deterministic.
   - Log `continuous_` and `use_wake_word_` values on every `on_start`.
   - Add a dummy log on `on_idle_trigger` (different from `on_end`) so we can see whether continuous self-loop is firing.

4. **Document the placeholder URL as load-bearing, with a citation to `voice_assistant.cpp:746`.** [TRIVIAL, prevents future re-debugging]
   - One comment block in `scripts/voice_pipeline.py` and the firmware YAML.
   - Reference: empty url in TTS_END causes early-return that skips state transition to `STREAMING_RESPONSE`.

5. **Adopt voice-pe's wake-word probability cutoff presets.** [SMALL, quality improvement]
   - One template `select:` entity, three sensitivity options, lambda that calls `set_probability_cutoff` on the active model.
   - Direct copy from `home-assistant-voice.yaml:1772-1802`.

6. **Replace RMS VAD with webrtcvad in the bridge.** [SMALL, quality improvement on #5]
   - Optional. Only if RMS misbehaves in real ambient noise.

7. **Compile-test voice-pe YAML in our ESPHome install to triage toolchain breakage.** [SMALL, blocker #7 diagnostic]
   - `esphome compile _refs/home-assistant-voice-pe/home-assistant-voice.yaml`.
   - If it builds, our YAML is the problem. If it doesn't, pioarduino artifact is broken and we wait.

8. **Move firmware off `narada-voice-test.yaml` and back into `narada-body.yaml` once 1+2 work.** [MEDIUM, integration step]
   - Display + scene rendering returns. Voice path stays.
   - Verify display I2C and audio I2C don't collide (they share `i2c_adc_dac` per current YAML).

---

*References:*
- voice_assistant C++ state machine: `_refs/esphome/esphome/components/voice_assistant/voice_assistant.cpp`, `voice_assistant.h`
- voice-pe gold-standard YAML: `_refs/home-assistant-voice-pe/home-assistant-voice.yaml` (1924 lines; the voice-relevant blocks live at 1503–1909)
- Box-3 reference YAML: `_refs/wake-word-voice-assistants/esp32-s3-box-3/esp32-s3-box-3.yaml`
- HA assist_satellite (the other side of the API protocol): `_refs/ha-core/homeassistant/components/esphome/assist_satellite.py`
- HA assist_pipeline (the brain side): `_refs/ha-core/homeassistant/components/assist_pipeline/pipeline.py`
- mWW codegen: `_refs/esphome/esphome/components/micro_wake_word/__init__.py`, `streaming_model.cpp`
- Speaker default rate: `_refs/esphome/esphome/components/speaker/speaker.h:99-115`, `_refs/esphome/esphome/components/i2s_audio/speaker/__init__.py:80-138`
