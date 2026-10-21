# BrainFrog Voice

A friendly frog who reads your Twitch chat out loud, in a voice you pick.

This is a plain background app, not a VR scene or an overlay: it has no window in your
headset at all. It just listens to your chat and talks through your speakers/headset
audio, so it keeps working no matter what you're playing -- VR, flatscreen, anything --
without needing any of the VR-overlay plumbing that doesn't actually exist outside
SteamVR today.

## How it works
`Twitch chat (anonymous, read-only) -> OpenRouter LLM (BrainFrog persona) -> Inworld TTS -> your speakers`

By default BrainFrog stays quiet until you ask. Three things the mic listens for:
- **"What's chat saying?"** (with or without the wake word) -- reads whatever's new since
  the last time you asked. Never repeats a message you've already heard: if nothing's
  arrived since last time, he says so instead of reading the same thing again.
- **Wake word + a question** ("BrainFrog, how's it going?") -- an actual answer, in
  character, not a chat reading.
- **Just the wake word** ("hey BrainFrog") -- starts a conversation; say whatever's on
  your mind.

While reading chat he sticks strictly to the messages -- no jokes or remarks mixed in, so
it's never ambiguous whether something was from chat or from him. In conversation, his
full personality is free to banter.

All of this runs through a small local speech-to-text model (faster-whisper) -- nothing
audio-related leaves your PC. You can also turn on automatic reading of every new message
if you'd rather not ask each time, though that can talk over your game at a bad moment,
which is why it's off by default.

## Run (Windows)
1. Install Python 3.10+.
2. Double-click **`START_BRAINFROG.bat`** in this folder. If double-clicking a `.bat` does
   nothing on your PC, double-click **`START_BRAINFROG.vbs`** instead. Either starts the
   app and opens its settings page. First run installs dependencies.
3. The settings page opens at http://127.0.0.1:5858. Enter your **Inworld** and
   **OpenRouter** keys, pick a voice, enter your Twitch channel, tick **Let BrainFrog
   read my live chat**, then **Save settings**.
4. Start your game (VR or otherwise) as usual, in whatever way you normally launch it.
   BrainFrog keeps running and reading chat in the background regardless.

Settings and keys are stored in `%USERPROFILE%\.brainfrog_voice\config.json`, outside this
repo. The server only listens on localhost.

### Keys you'll need
- **Inworld** (text-to-speech): pick any voice from your Inworld account, or paste a
  Voice ID directly if the list doesn't load.
- **OpenRouter** (the language model that gives BrainFrog his personality): any chat
  model slug works; the default is a small, fast one.

## Settings

| Section | What it controls |
|---|---|
| Voice (Inworld) | API key, which voice BrainFrog speaks with, speaking rate, volume. **Preview voice** plays a test line with the current settings. |
| Brain (OpenRouter) | API key, model, and an optional free-text box for extra personality notes (e.g. "mention my channel name sometimes"). |
| Twitch chat | Enable/disable, channel name, how many messages get read per batch, the bot-ignore list, a custom blocked-words list, the slur filter toggle, and an opt-in "also read automatically whenever new messages arrive" switch (off by default). **Read chat now** forces an immediate reading. |
| Wake word | Enable/disable the mic listener, the wake word itself (default "brainfrog"), the local speech-recognition model size, mic sensitivity, a live mic-level meter, and an **Ask** box to try a question without a mic. |

## Persona
BrainFrog's personality lives in `app/frog_voice/persona.py`. `CORE_PERSONA` (who he is,
how he talks) always applies; on top of that, `CHAT_READING_RULES` (strictly the
messages, no commentary) is used only while reading chat, and `TALK_RULES` (full
personality, banter welcome) only during an actual conversation. The "extra personality
notes" field on the settings page layers on top of either, without touching code.

## Safety
Chat text from viewers is always handed to the model inside a clearly marked, explicitly
untrusted block, with instructions never to follow anything inside it -- just to read it
aloud. A built-in filter (on by default) also skips any message or username containing a
slur, resistant to the usual symbol/spacing tricks, and you can add your own blocked words
on the settings page. Anything a moderator deletes, or from a banned/timed-out user, is
removed from what BrainFrog has buffered, so he can't read out something that was taken
down. None of this is a guarantee against a determined viewer -- keep an eye on your
blocked-words list if this is live on stream.

## Tests
```
cd app && python -m unittest discover -s tests
```

## Project layout
```
app/
  server.py              Local Flask server + API, binds to 127.0.0.1 only
  frog_voice/
    config.py            Settings persisted to ~/.brainfrog_voice/config.json
    persona.py           BrainFrog's personality (system prompt)
    twitch.py            Anonymous Twitch IRC client, moderation-aware buffer, cursor
    slurs.py             Slur/evasion detection used to filter chat before it's read
    engine.py            Watches chat, batches new messages, drives the LLM + TTS
    wake.py              Mic listener: VAD segmentation + wake-word/chat-request detection
    llm.py               OpenRouter chat completions (streaming)
    inworld.py            Inworld text-to-speech
    pipeline.py           Streams LLM sentences into TTS with no gaps between them
    streaming.py          Turns a token stream into whole sentences
    speech_io.py          MP3 playback + local speech-to-text (faster-whisper)
    lifecycle.py          Clean shutdown when the console window closes
  web/index.html          Settings page
  tests/                  Unit tests (no network, no real audio)
```
