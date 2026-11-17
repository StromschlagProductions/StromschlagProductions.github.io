# Vorlage für neue Stromschlag-Plugins

Die Datei `windows-vst3-release.yml` in diesem Verzeichnis ist eine kopierbare Ausgangsvorlage, **kein** automatisch aktiver Workflow. Bei einem neuen JUCE-Plugin die Platzhalter `PLUGIN_NAME`, `PLUGIN_TARGET` und `PLUGIN_VERSION_FILE` ersetzen und als `.github/workflows/build.yml` im neuen Repository speichern.

Der Workflow ist absichtlich nur manuell ausführbar und veröffentlicht ausschließlich nach `publish=true` auf `main`, wenn Build, CTest, Herstellerprüfung und pluginval Level 8 erfolgreich waren. Vor dem ersten Release unbedingt in einer Testausführung mit `publish=false` prüfen, dass Build-Pfad und CMake-Projekt zum Plugin passen.

Das neue Plugin muss anschließend einmalig auf der Homepage ergänzt werden (`data-release-repo` + Fallback `/releases/latest`). Danach läuft die Aktualisierung des Download-Buttons automatisch.
