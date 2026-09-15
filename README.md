# VDXR Twitch Chat

A small, grabbable VR panel that shows your live Twitch chat. Built with Godot 4's
built-in OpenXR support, meant to run through Virtual Desktop's own OpenXR runtime
(VDXR) instead of SteamVR.

## What this is (and isn't)

This is a **standalone VR app**: it boots its own OpenXR session, shows the chat
panel, and lets you grab/move/lock it. It is **not** an overlay that floats on top
of a separate game while that game is also running.

That limitation isn't a shortcut taken here — it's a real gap in the ecosystem
today. LIV can overlay games on SteamVR because SteamVR exposes `IVROverlay`, a
compositor-level API for a second app to draw on top of another app's view.
Vanilla OpenXR has an equivalent concept (`XR_EXTX_overlay`), but as of writing:

- Virtual Desktop's VDXR runtime does not implement it.
- Godot's OpenXR integration doesn't fully support it either (the extension has
  had an open, unmerged draft PR since 2021).

So there is currently no clean way to have this app render "over" another OpenXR
game via VDXR. If that ever changes upstream, this app's grab/lock logic doesn't
need to change — only the session setup would need an overlay flag.

In the meantime, if you want chat visible *while actively gaming*, Virtual
Desktop's own in-headset dashboard/browser panel (bring it up with your usual VD
shortcut) can show a browser pointed at Twitch's own chat popout
(`https://www.twitch.tv/popout/<channel>/chat`) — that rides on VD's own
compositor rather than needing OpenXR overlay support.

## Requirements

- [Godot 4.3+](https://godotengine.org/download) (Standard build; no C# needed).
- Virtual Desktop, with **Streaming > Developer > OpenXR Runtime** set to
  "Virtual Desktop" (VDXR) instead of SteamVR.
- A Quest (or other headset supported by Virtual Desktop) connected via VD.

## Setup

1. Edit `config.ini` in this folder and set your channel name:
   ```ini
   [twitch]
   channel="your_channel_name"
   ```
2. Open the project in Godot (`project.godot`).
3. Start Virtual Desktop and make sure VDXR is the active OpenXR runtime
   (Virtual Desktop Streaming settings > Developer > OpenXR Runtime).
4. Run the project (F5) with your headset connected. It should launch straight
   into VR with the chat panel floating in front of you.

To run outside the editor, export it (Project > Export) as a Windows Desktop
build, then launch the resulting `.exe` with Virtual Desktop's OpenXR runtime
active. You can override the channel per-launch without touching `config.ini`:

```
VDXRTwitchChat.exe --channel=your_channel_name
```

## Controls

- **Grip button**: grab the chat panel when your hand is near it; move it
  anywhere in space.
- **Face button (A/X)** while holding it: lock the panel to that hand at its
  current offset — hold it against your forearm and lock it there to get a
  wrist-mounted chat display. Press again to unlock and leave it floating
  freely in world space wherever it currently is.

## How it works

- `scripts/twitch_chat_client.gd` — autoloaded singleton (`TwitchChat`) that
  connects anonymously (read-only, no OAuth token needed) to Twitch's IRC-over-
  WebSocket endpoint, joins your channel, and emits a signal per chat message
  (with the sender's name and Twitch-assigned color). It auto-reconnects if the
  connection drops.
- `scripts/chat_display.gd` — feeds incoming messages into a `RichTextLabel`
  inside a `SubViewport`, capped to the last 150 lines, auto-scrolling.
- `scripts/panel_mesh_setup.gd` — projects that `SubViewport`'s live texture
  onto a small unshaded quad in 3D space, which is what you actually see and
  grab in VR.
- `scripts/grabbable_chat_panel.gd` — grab/lock interaction described above.
- `scripts/xr_manager.gd` — initializes the OpenXR session on startup.

## Troubleshooting

- **Nothing happens / no VR view**: check the Godot output console for the
  OpenXR error. Most commonly VDXR isn't the active runtime, or Virtual Desktop
  isn't streaming yet when you press Play.
- **Panel shows "connecting..." forever**: check your internet connection and
  that the channel name in `config.ini` is spelled correctly (no `#` prefix).
- **Grip/lock buttons don't respond**: these use Godot's default OpenXR action
  names (`grip_click`, `ax_button`). If your controller binding differs, open
  Project Settings > XR > OpenXR > Action Map and confirm those actions are
  bound, or adjust the constants at the top of `grabbable_chat_panel.gd`.
