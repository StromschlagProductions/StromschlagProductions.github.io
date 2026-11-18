# SID Heartbeat Studio

Browser-App für C64-Musik: Noten in einer Piano-Roll setzen, Songs für den C64 Ultimate (Heartbeat-Soundtracker) lesen und schreiben, `.sid`-Dateien importieren und als `.sid` exportieren.

**Starten:** <https://stromschlagproductions.github.io/sid-studio/>
Die App lässt sich im Browser installieren (Chrome/Edge: Symbol in der Adressleiste) und läuft dann auch ohne Internet. Die Datei `index.html` ist die komplette App und kann auch einzeln heruntergeladen und per Doppelklick geöffnet werden.

Alle Songs und Einstellungen bleiben im eigenen Browser, es werden keine Daten gesendet.

## Aufbau

- `index.html`: die ganze App in einer Datei (Oberfläche, Player, SID-Emulation als WebAssembly, Schriften). Der JavaScript-Teil ist unverkleinert lesbar.
- `quellcode/resid/`: der reSID-Quelltext, aus dem die WebAssembly-Datei gebaut ist (mit einer kleinen Korrektur für schnell aufeinanderfolgende Registerschreibzugriffe).
- `quellcode/shim/`: die Hülle (`wrap.cc`), die reSID für den Browser ansprechbar macht.
- `sw.js`, `manifest.webmanifest`, `icon-*.png`: Offline-Funktion und Installation.

## Lizenz

Die App enthält reSID (© Dag Lem und Mitwirkende, GNU GPL Version 2 oder später) und steht deshalb insgesamt unter der **GNU GPL Version 2 oder später** (siehe `LICENSE`). Die Schriften IBM Plex und Pixelify Sans stehen unter der SIL Open Font License 1.1.

*Das Studio soll das Komponieren und Lernen nicht ersetzen, sondern die technische Umsetzung einfacher machen; dankbar für den selbst gegangenen Weg.*

– Lars Eickstädt, Stromschlag Audio
