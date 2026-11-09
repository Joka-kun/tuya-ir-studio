<p align="center"><img src="assets/banner.svg" alt="Tuya IR Studio" width="100%"></p>

<p align="center"><a href="README.md">English</a> &nbsp;·&nbsp; <a href="README_RU.md">Русский</a> &nbsp;·&nbsp; <a href="README_DE.md">Deutsch</a> &nbsp;·&nbsp; <a href="README_FR.md">Français</a> &nbsp;·&nbsp; <a href="README_ES.md">Español</a> &nbsp;·&nbsp; <a href="README_ZH.md">中文</a></p>

<p align="center">
  <a href="https://github.com/Joka-kun/tuya-ir-studio/actions/workflows/tests.yaml"><img src="https://img.shields.io/github/actions/workflow/status/Joka-kun/tuya-ir-studio/tests.yaml?branch=main&amp;label=tests&amp;style=flat-square" alt="Pruebas"></a>
  <a href="https://github.com/Joka-kun/tuya-ir-studio/releases"><img src="https://img.shields.io/github/v/release/Joka-kun/tuya-ir-studio?label=release&amp;style=flat-square" alt="Última versión"></a>
  <a href="https://www.home-assistant.io/integrations/marketplace/"><img src="https://img.shields.io/badge/Marketplace-listed-18A4CB?style=flat-square&amp;logo=homeassistant&amp;logoColor=white" alt="Catálogo Marketplace"></a>
  <a href="docs/NATIVE_CONFIGURE.md"><img src="https://img.shields.io/badge/control-local%20IR-0F766E?style=flat-square" alt="IR local"></a>
</p>

# Tuya IR Studio

**Mandos infrarrojos locales para Home Assistant.** Conecta una pasarela IR Tuya compatible, crea mandos, aprende señales con el mando físico original y controla los dispositivos a través de tu red local.

**Importante:** se ha eliminado la importación experimental de botones de Smart Life. Antes podía recuperar nombres técnicos sin señales IR funcionales. El inicio de sesión por QR se utiliza **solo para configurar la pasarela**, no para importar botones o códigos de la nube.

<p align="center"><img src="assets/workflow.svg" alt="Conectar pasarela, crear mando, aprender botones y controlar en la red local" width="100%"></p>

## Funciones

- **Configuración de pasarela:** acceso QR de Tuya / Smart Life o conexión manual mediante IP, Device ID y Local Key.
- **Editor de mandos:** crear, renombrar y ordenar perfiles y botones; seleccionar tipo e icono del dispositivo.
- **Aprendizaje guiado:** capturar las señales IR reales desde el mando original.
- **Control local:** enviar los comandos almacenados mediante entidades `remote.*` de Home Assistant.
- **Opciones avanzadas:** archivos Flipper `.ir` compatibles, códigos manuales y copias de seguridad.

## Instalación

En **Ajustes → Marketplace** (antes **HACS**), busca **Tuya IR Studio** e instala la integración desde el catálogo.

En **Ajustes → Dispositivos y servicios → Añadir integración → Tuya IR Studio**, configura tu pasarela. Después abre la barra lateral, crea un mando, añade botones y utiliza el **aprendizaje paso a paso**. Comprueba que el aparato responda físicamente.

## Limitaciones

No se generan botones según la categoría del dispositivo ni se importan diseños de Smart Life. Los mandos RF, Bluetooth y HDMI-CEC no son IR. Algunos aires acondicionados necesitan tramas de estado completas. El envío local puede funcionar sin Internet tras la configuración, aunque la autorización QR puede necesitar conexión a Tuya.

[Guía de configuración (inglés)](docs/TUYA_ONBOARDING.md) · [Hoja de ruta (inglés)](ROADMAP.md) · [Cambios](CHANGELOG.md) · [Informar de problemas](https://github.com/Joka-kun/tuya-ir-studio/issues)

Licencia MIT. Proyecto independiente de código abierto.