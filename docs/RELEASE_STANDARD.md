# Stromschlag Productions – Release-Standard

## Ziel

Alle Audio-Plugins werden unabhängig vom Entwicklungswerkzeug (Claude, Codex, ChatGPT oder lokal) über GitHub veröffentlicht. Ein Push ist **kein** Release. Neue Downloads erscheinen erst nach einer bestandenen Abnahme und ausdrücklicher Veröffentlichungsfreigabe. Die Homepage ermittelt automatisch das neueste stabile GitHub-Release je Plugin.

## Verbindlicher Ablauf

1. Änderungen auf einem Entwicklungszweig erstellen und Tests ausführen.
2. Nach Review in `main` integrieren; `main` darf Entwicklungscode enthalten, ohne dass er sofort als fertige Version veröffentlicht wird.
3. Die Windows-VST3-Abnahme ausführen: Build, Regressionstests und pluginval Strictness 8. Fehlgeschlagene Prüfungen blockieren die Veröffentlichung.
4. Die Veröffentlichung ausdrücklich freigeben. Für Locations, Radiophone, Dreamcatcher, Doppelganger und Gale: Actions → **Windows-VST3 bauen** → **Run workflow**, Branch `main`, Option `publish=true`. Die Workflows prüfen die Herstellerangabe `Stromschlag Audio`. Für SpatialLab: separater, strengerer zweistufiger Prozess über **Build and test** und **Publish verified SPATIAL LAB release** mit Tag und zugehöriger erfolgreicher Abnahme.
5. Erst wenn ein öffentliches, nicht als Prerelease markiertes Release mit hochgeladener Windows-VST3-ZIP existiert, ist es für die Homepage verfügbar.
6. Prüfen: `https://api.github.com/repos/StromschlagProductions/REPOSITORY/releases/latest` muss den neuen Tag und eine Windows-VST3-ZIP enthalten. GitHub Pages ruft diese Information zur Laufzeit ab. Bei API-Ausfall führen Download-Buttons auf `/releases/latest`, nicht auf veraltete ZIPs.

## Neue Plugins

- Neues öffentliches GitHub-Repository unter `StromschlagProductions` anlegen.
- CI-Workflow mit manueller `publish`-Freigabe und Tests übernehmen. Ein Standard-Workflow muss auf `main` beschränkt sein, eine Windows-VST3-ZIP als Release-Asset anhängen und `make_latest: true` setzen.
- `VERSION` und Release-Hinweise nach dem jeweiligen Plugin-Schema pflegen. Tags müssen eindeutig sein und zur getesteten Version passen.
- Auf der Homepage eine Plugin-Karte mit `data-release-repo="NEUES-REPO"` und einem Fallback-Link auf `https://github.com/StromschlagProductions/NEUES-REPO/releases/latest` ergänzen. Die bestehende JavaScript-Auflösung benötigt danach keine weitere Anpassung.
- Nach der ersten Veröffentlichung die Homepage-Download-Schaltfläche und ZIP-Inhalt prüfen.

## Bewusste Grenzen

- Es gibt **keine** automatische Veröffentlichung bei jedem Push oder Merge. Das verhindert die Auslieferung unfertiger oder ungetesteter Änderungen und spart Windows-Actions-Minuten.
- Es gibt derzeit **keinen** organisationsweiten GitHub-Repository-Template-Automatismus, der diese Dateien in jedes neue Repo kopiert. Dieses Dokument ist die verbindliche Checkliste, bis ein eigenständiges Template-Repository eingerichtet ist.
- Die Homepage erkennt neue Repositories nicht von selbst; jede neue Plugin-Karte muss einmalig hinzugefügt werden.
- Die automatische Abfrage ist clientseitig und kann durch Browser-Sperren oder GitHub-API-Limits fehlschlagen; der Fallback führt dann zur aktuellen Release-Seite.

## Hersteller- und KI-Attribution

Die vier regulären Windows-Build-Workflows prüfen die JUCE/CMake-Herstellerangabe auf `Stromschlag Audio`. SPATIAL LAB verwendet bereits eine eigene umfassende VST3-Hersteller- und Identitätsprüfung. Alle fünf Repositories enthalten `docs/PUBLISHING.md` als einheitliche Veröffentlichungsvorgabe. Claude, Codex und ChatGPT sind Entwicklungswerkzeuge, keine Plugin-Hersteller. Historische Commit-Autoren/Co-Autoren werden nicht rückwirkend verändert; Drittanbieter-Lizenzen und Urheberrechtshinweise bleiben bestehen.
