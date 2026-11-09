<p align="center"><img src="assets/banner.svg" alt="Tuya IR Studio" width="100%"></p>

<p align="center"><a href="README.md">English</a> &nbsp;·&nbsp; <a href="README_RU.md">Русский</a> &nbsp;·&nbsp; <a href="README_DE.md">Deutsch</a> &nbsp;·&nbsp; <a href="README_FR.md">Français</a> &nbsp;·&nbsp; <a href="README_ES.md">Español</a> &nbsp;·&nbsp; <a href="README_ZH.md">中文</a></p>

# Tuya IR Studio

**Télécommandes infrarouges locales pour Home Assistant.** Connectez une passerelle IR Tuya compatible, créez vos télécommandes, apprenez les signaux avec la télécommande d'origine et pilotez vos appareils sur le réseau local.

**Important :** l'import expérimental des touches Smart Life a été supprimé. Il pouvait récupérer des noms techniques sans véritables signaux IR. L'authentification QR sert **uniquement à configurer la passerelle**, et non à télécharger des touches ou codes cloud.

<p align="center"><img src="assets/workflow.svg" alt="Connecter la passerelle, créer une télécommande, apprendre les touches, contrôler en local" width="100%"></p>

## Fonctionnalités

- **Configuration de passerelle :** connexion QR Tuya / Smart Life ou saisie manuelle de l'adresse IP, du Device ID et de la Local Key.
- **Éditeur de télécommandes :** création, renommage et réorganisation des profils et des touches ; choix du type d'appareil et de son icône.
- **Apprentissage guidé :** réception des vrais signaux IR grâce à la télécommande physique d'origine.
- **Commande locale :** émission des commandes enregistrées via une entité `remote.*` de Home Assistant.
- **Options avancées :** fichiers Flipper `.ir` compatibles, codes manuels et sauvegardes.

## Installation

Dans **Paramètres → Marketplace** (anciennement **HACS**), recherchez **Tuya IR Studio** et installez l'intégration depuis le catalogue.

Ouvrez **Paramètres → Appareils et services → Ajouter une intégration → Tuya IR Studio** pour configurer la passerelle. Créez ensuite une télécommande dans la barre latérale, ajoutez les touches nécessaires et lancez **l'apprentissage pas à pas**. Vérifiez la réaction de l'appareil réel.

## Limites

Aucune touche n'est inventée à partir d'une catégorie d'appareil et aucune disposition Smart Life n'est importée automatiquement. Les télécommandes RF, Bluetooth ou HDMI-CEC ne sont pas de l'IR. Certains climatiseurs utilisent des trames d'état complètes. Les commandes IR locales peuvent fonctionner sans Internet après la configuration, mais l'authentification QR peut nécessiter le cloud Tuya.

[Guide d'installation (anglais)](docs/TUYA_ONBOARDING.md) · [Feuille de route (anglais)](ROADMAP.md) · [Historique](CHANGELOG.md) · [Signaler un problème](https://github.com/Joka-kun/tuya-ir-studio/issues)

Licence MIT. Projet open source indépendant.