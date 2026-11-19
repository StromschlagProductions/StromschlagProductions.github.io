# Automatisches Windows-VST3-Bundle

Die Homepage verlinkt ein vorab geprüftes Release-ZIP:

https://github.com/StromschlagProductions/StromschlagProductions.github.io/releases/latest/download/Stromschlag-Audio-Plugin-Bundle.zip

## Erkennung ohne feste Plugin-Liste

`scripts/build_bundle.py` listet alle öffentlichen, nicht geforkten Repositories des Kontos `StromschlagProductions` mit Pagination auf. Das funktioniert auch bei einem GitHub-Organisationskonto. Repositorynamen allein reichen nicht aus.

Ein Kandidat benötigt ein veröffentlichtes stabiles Latest-Release, ein `CMakeLists.txt` am Release-Tag mit `juce_add_plugin`, VST3 und `COMPANY_NAME "Stromschlag Audio"`, sowie genau ein zum Produkt passendes Windows-VST3-ZIP. Drafts, Prereleases und nicht hochgeladene Assets werden ausgeschlossen. Neue Repositories mit denselben Konventionen werden ohne Konfigurationsänderung aufgenommen.

Vor Aufnahme werden sämtliche ZIP-Dateien vollständig gelesen (CRC), Dateigrößen und vorhandene GitHub-SHA256-Digests geprüft. Das direkt enthaltene VST3-Verzeichnis muss zum CMake-Produkt passen. `Contents/Resources/moduleinfo.json` muss Produkt, Release-Version, Hersteller `Stromschlag Audio` und gültige Audio-Module-Klassen ausweisen. Das eigentliche Modul unter `Contents/x86_64-win` muss eine Windows-PE-Datei für AMD64 sein. JUCE-Metadaten mit abschließenden Kommas werden unterstützt. Verzeichnisnamen und Audio-Class-IDs dürfen nicht kollidieren.

Pfade mit Traversal, Backslashes, absoluten/Windows-Laufwerkspfaden, reservierten Windows-Namen, Symlinks und doppelten Einträgen werden verworfen. Archiv- und Entpackgrößen sind begrenzt. Module werden nur geprüft/verpackt, nie ausgeführt. Das Verfahren identifiziert passende veröffentlichte VST3-Pakete; es ersetzt keine klangliche oder Host-Abnahme.

Ungeeignete neue Kandidaten werden mit Grund protokolliert. Repositories im letzten veröffentlichten Manifest gelten als bereits aufgenommen: Wenn eines davon verschwindet oder sein neues Release ungültig ist, wird der ganze Veröffentlichungslauf abgebrochen. So wird kein verkleinertes Update stillschweigend ausgeliefert. Veränderte Release-Konventionen erfordern eine Anpassung des Erkennungsverfahrens, keine laufende Versions- oder Linkpflege.

## Ablauf und Auslöser

`.github/workflows/plugin-bundle.yml` prüft stündlich um Minute 17; GitHub kann geplante Läufe verzögern. Neue Versionen und neue Repositories werden beim nächsten Lauf erkannt. Außerdem sind `workflow_dispatch` und optional `repository_dispatch` mit Typ `plugin-release` vorhanden. Es werden keine Änderungen in den Plugin-Repositories und keine zusätzlichen Secrets benötigt.

Ein Fingerabdruck umfasst validierte Repositories, Release-/Asset-IDs, Dateinamen, Aktualisierungszeitpunkte, Prüfsummen und Builder-Code. Unveränderter Inhalt erzeugt kein neues Release. Ein geänderter Builder erzeugt ein neues, erneut geprüftes Paket. Derzeit werden auch bei unverändertem Bestand die Archive erneut geprüft; der lokale Cache spart innerhalb eines Arbeitsverzeichnisses Downloads. Flüchtige Actions-Runner beginnen ohne Cache.

Die Workflow-Tests laufen mit `contents: read`; ausschließlich der Veröffentlichungsjob erhält `contents: write`. Gleichzeitige Veröffentlichungen werden serialisiert. Veröffentlichungen auf Pull Requests sind ausgeschlossen, und Checkout speichert keine Credentials. Es genügt der eingebaute `GITHUB_TOKEN`.

GitHub deaktiviert Zeitpläne öffentlicher Repositories nach 60 Tagen ohne Aktivität. Damit die Erkennung nach einer längeren Releasepause weiterläuft, schreibt ein erfolgreicher Lauf höchstens nach 45 Tagen ohne Commit auf `main` einen Zeitstempel in `.github/bundle-heartbeat.txt`. Das ist ein kleiner automatischer Wartungscommit, kein neues Bundle-Release; er löst den Bundle-Push-Trigger nicht erneut aus. Geschützte Branches, die solche Commits verhindern, müssen entsprechend eingerichtet werden; sonst wird dieser Wartungsschritt sichtbar fehlschlagen.

## Veröffentlichung ohne zerstörten Vorgänger

Ein neuer Inhalt erhält ein eigenes Tag `bundle-<Fingerabdruck>`. Zuerst entsteht ein Draft. ZIP, Manifest und SHA256-Datei werden hochgeladen, anschließend erneut heruntergeladen und byteweise über SHA256 geprüft. Erst danach wird der Draft veröffentlicht und als Latest markiert. Bei einem Fehler bleibt der bisherige Latest-Download erhalten. Ein unterbrochener Draft desselben Fingerabdrucks kann beim nächsten Lauf vervollständigt werden. Veröffentlichte Pakete werden nicht überschrieben oder gelöscht.

Das Manifest des letzten veröffentlichten Bundles steuert Vollständigkeit und Änderungsprüfung. Einzelne Plugin-Downloads und deren bestehendes Homepage-JavaScript bleiben unabhängig davon.

## Installation und Struktur

Im ZIP liegen die vollständigen originalen `.vst3`-Verzeichnisse unmittelbar an der Wurzel, ohne zusätzliche Windows-, Versions- oder Plugin-Unterordner. Alle enthaltenen Ressourcen werden unverändert mitgenommen. Außerdem: `VERSIONEN.txt`, `INSTALLATION.txt`, `bundle-manifest.json`. Außerhalb der Module gelieferte rechtliche Hinweise werden unter `LIZENZEN/<Produkt>/` bewahrt. Keine verschachtelten Download-ZIPs und keine Testdateien.

Alle `.vst3`-Ordner nach dem Entpacken direkt nach `C:\Program Files\Common Files\VST3\` kopieren; vorher die DAW schließen und bisherige Versionen sichern.

## Lokale Prüfung

Python 3.12, nur Standardbibliothek:

```
python -m unittest discover -s tests -v
python scripts/build_bundle.py --out bundle-output
python scripts/build_bundle.py --out bundle-output --previous bundle-output/bundle-manifest.json
```

Der letzte Befehl muss bei unveränderten Releases `UNCHANGED` ausgeben. Ohne `--publish` werden keine externen Änderungen vorgenommen. Zum Veröffentlichen benötigt der Actions-Job zusätzlich `gh`, `GH_TOKEN`, `GITHUB_SHA` und Schreibrecht für Releases.

Falls die automatische Veröffentlichung blockiert wird: Actions muss aktiviert sein; `main` muss der Default-Branch sein. Die Organisations-/Repository-Richtlinien müssen `contents: write` für den Job zulassen. Der spätere Heartbeat benötigt direkte Inhaltsänderungen auf `main`. Fehlende Rechte werden nicht durch einen PAT oder externen Dienst umgangen.
