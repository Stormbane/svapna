# mWW silent failure — root cause and fix

*2026-05-01 · why "okay nabu" did nothing on narada-voice-test*

## Root cause

**`micro_wake_word` boots in STOPPED state and only runs inference after an explicit `micro_wake_word.start:` action is fired.** Our YAML never fires that action. The component sits inert; the inference task never starts; the wake word never fires.

This is by design in the C++. From `_refs/esphome/esphome/components/micro_wake_word/micro_wake_word.cpp:344-374`:

```cpp
void MicroWakeWord::start() {
  ...
  this->pending_start_ = true;
  this->pending_stop_ = false;
}
void MicroWakeWord::stop() {
  ...
  this->pending_start_ = false;
  this->pending_stop_ = true;
}
```

The component's setup leaves it in `State::STOPPED`. The inference task in `inference_task_` (`micro_wake_word.cpp:154-209`) only runs while `pending_start_` is true. No automation that calls `start()` = no inference = no wake word.

## What the references do

**voice-pe** (`_refs/home-assistant-voice-pe/home-assistant-voice.yaml:1815-1817`):

```yaml
voice_assistant:
  on_client_connected:
    - lambda: id(init_in_progress) = false;
    - micro_wake_word.start:    # <-- the missing line
    - lambda: id(voice_assistant_phase) = ${voice_assist_idle_phase_id};
    - script.execute: control_leds
```

**box-3 reference** (`_refs/wake-word-voice-assistants/esp32-s3-box-3/esp32-s3-box-3.yaml:312-314, 281-286`):

```yaml
voice_assistant:
  on_client_connected:
    - lambda: id(init_in_progress) = false;
    - script.execute: start_wake_word    # script that calls micro_wake_word.start

  on_end:
    # Restart only mWW if enabled; streaming wake words automatically restart
    - if:
        condition:
          - lambda: return id(wake_word_engine_location).current_option() == "On device";
        then:
          - lambda: id(va).set_use_wake_word(false);
          - micro_wake_word.start:   # <-- restart after each turn
```

Both patterns:
1. Start mWW on `on_client_connected` (when the bridge subscribes).
2. Restart mWW on `on_end` (after each turn — `voice_assistant.start:` auto-stops mWW when a turn begins).

We had neither.

## The fix

Two YAML edits:

```yaml
voice_assistant:
  on_client_connected:
    - logger.log: "va: client_connected (pipeline subscribed)"
    - micro_wake_word.start:        # <-- ADDED
  on_client_disconnected:
    - logger.log: "va: client_disconnected"
    - micro_wake_word.stop:         # <-- ADDED (clean shutdown)
  ...
  on_end:
    - logger.log: "va: on_end (back to idle)"
    - micro_wake_word.start:        # <-- ADDED (restart after turn)
```

Both applied to `embodiment/firmware/narada-voice-test.yaml`.

## What to look for in device logs after re-flash

When the bridge connects, expect:

```
[va: client_connected (pipeline subscribed)]
[micro_wake_word: ...]    <-- model load, tensor arena probe
[micro_wake_word:DEBUG: Probed tensor arena size: %zu bytes]
[micro_wake_word:DEBUG: Inference task has started, attempting to allocate memory for buffers]
```

When you say "okay nabu":

```
[mww FIRED: okay_nabu]    <-- our debug log line
[va: on_start]
```

If the tensor arena log is absent AND no inference-started log: the alloc failed, even with PSRAM rodata flags. Next escalation: per-model `tensor_arena_size:` override.

If inference starts but no FIRED log on speech: the probability_cutoff is too high for our gain settings. voice-pe ships three sensitivity presets at `home-assistant-voice.yaml:1791-1801`; the most-sensitive preset for okay_nabu is **143/255** (~0.56). The manifest default is 217/255 (~0.85). Override per-model:

```yaml
micro_wake_word:
  models:
    - model: okay_nabu
      probability_cutoff: 0.56     # voice-pe's "slightly sensitive" preset
```

## Things that are NOT the problem (ruled out)

- **Microphone contention.** The box-3 reference shares `box_mic` between voice_assistant and mWW exactly as we do; that topology works.
- **PSRAM rodata flags.** They're correct and necessary. Just not sufficient on their own.
- **`channels: 0` vs `channels: 1`.** Correct for our mono mic — voice-pe uses `1` because their mic is stereo and they want the right channel.
- **Lambda syntax for wake_word.** `!lambda return wake_word;` is right; matches voice-pe and box-3 exactly.
- **JSON output of `claude -p`.** Verified — `result` and `session_id` fields are present.

## What this also explains

The phantom-turn diagnosis from yesterday's journal entry was wrong about the cause but right that *something* was off. The phantom turns weren't from HA-side wake word streaming or continuous mode — they were from the touchscreen, because mWW was inert. Touch was the only thing capable of starting a turn.

## Risk

Re-flash, watch the logs. If mWW now fires: we have full voice round-trip working on the new architecture. If mWW logs an alloc failure or inference error: we move to the per-model `tensor_arena_size` and `probability_cutoff` overrides above.
