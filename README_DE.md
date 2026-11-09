<p align="center"><img src="assets/banner.svg" alt="Tuya IR Studio" width="100%"></p>

<p align="center"><a href="README.md">English</a> &nbsp;·&nbsp; <a href="README_RU.md">Русский</a> &nbsp;·&nbsp; <a href="README_DE.md">Deutsch</a> &nbsp;·&nbsp; <a href="README_FR.md">Français</a> &nbsp;·&nbsp; <a href="README_ES.md">Español</a> &nbsp;·&nbsp; <a href="README_ZH.md">中文</a></p>

# Tuya IR Studio

**Lokale Infrarot-Fernbedienungen für Home Assistant.** Verbinde ein kompatibles Tuya-IR-Gateway, erstelle Fernbedienungen, lerne Signale mit der Originalfernbedienung an und steuere deine Geräte im lokalen Netzwerk.

**Wichtig:** Der experimentelle Import von Smart-Life-Fernbedienungstasten wurde entfernt. Die Funktion lieferte teilweise nur technische Bezeichnungen, aber keine funktionsfähigen Infrarotsignale. Die QR-Anmeldung dient **ausschließlich zur Einrichtung des Gateways**, nicht zum Import von Cloud-Tasten oder IR-Codes.

<p align="center"><img src="assets/workflow.svg" alt="Gateway verbinden, Fernbedienung erstellen, Tasten anlernen, lokal steuern" width="100%"></p>

## Funktionen

- **Gateway-Einrichtung:** Tuya/Smart-Life-QR-Anmeldung oder manuelle Konfiguration mit IP-Adresse, Device ID und Local Key.
- **Fernbedienungseditor:** Profile und Tasten erstellen, umbenennen und sortieren; Gerätetyp und Symbol auswählen.
- **Anlernen:** Schrittweises Einlesen von IR-Signalen über das kompatible Gateway mit der Originalfernbedienung.
- **Lokale Steuerung:** Gespeicherte Befehle über Home-Assistant-`remote.*`-Entitäten versenden.
- **Erweiterte Funktionen:** Unterstützte Flipper-`.ir`-Dateien, manuelle Codes und Sicherungskopien.

## Installation

Unter **Einstellungen → Marketplace** (früher **HACS**) nach **Tuya IR Studio** suchen und die Integration aus dem Katalog installieren.

Über **Einstellungen → Geräte & Dienste → Integration hinzufügen → Tuya IR Studio** das Gateway einrichten. Danach in der Seitenleiste eine Fernbedienung anlegen, Tasten hinzufügen und **schrittweise anlernen**. Die tatsächliche Reaktion des Zielgeräts prüfen.

## Wichtige Hinweise

IR Studio erfindet keine Tasten anhand der Gerätekategorie und importiert keine Smart-Life-Cloud-Fernbedienungen automatisch. Funk (RF), Bluetooth und HDMI-CEC sind keine IR-Signale. Bei Klimaanlagen können vollständige Zustandsbefehle nötig sein. Lokales Senden kann nach der Einrichtung ohne Internet funktionieren; für QR-Einrichtung kann Tuya-Konnektivität notwendig sein.

[Einrichtungsanleitung (Englisch)](docs/TUYA_ONBOARDING.md) · [Roadmap (Englisch)](ROADMAP.md) · [Changelog](CHANGELOG.md) · [Probleme melden](https://github.com/Joka-kun/tuya-ir-studio/issues)

MIT-Lizenz. Unabhängiges Open-Source-Projekt.