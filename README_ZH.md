<p align="center"><img src="assets/banner.svg" alt="Tuya IR Studio" width="100%"></p>

<p align="center"><a href="README.md">English</a> &nbsp;·&nbsp; <a href="README_RU.md">Русский</a> &nbsp;·&nbsp; <a href="README_DE.md">Deutsch</a> &nbsp;·&nbsp; <a href="README_FR.md">Français</a> &nbsp;·&nbsp; <a href="README_ES.md">Español</a> &nbsp;·&nbsp; <a href="README_ZH.md">中文</a></p>

<p align="center">
  <a href="https://github.com/Joka-kun/tuya-ir-studio/actions/workflows/tests.yaml"><img src="https://img.shields.io/github/actions/workflow/status/Joka-kun/tuya-ir-studio/tests.yaml?branch=main&amp;label=tests&amp;style=flat-square" alt="测试"></a>
  <a href="https://github.com/Joka-kun/tuya-ir-studio/releases"><img src="https://img.shields.io/github/v/release/Joka-kun/tuya-ir-studio?label=release&amp;style=flat-square" alt="最新版本"></a>
  <a href="https://www.home-assistant.io/integrations/marketplace/"><img src="https://img.shields.io/badge/Marketplace-listed-18A4CB?style=flat-square&amp;logo=homeassistant&amp;logoColor=white" alt="已收录 Marketplace"></a>
  <a href="docs/NATIVE_CONFIGURE.md"><img src="https://img.shields.io/badge/control-local%20IR-0F766E?style=flat-square" alt="本地红外"></a>
</p>

# Tuya IR Studio

**专为 Home Assistant 打造的本地红外遥控管理工具。** 连接兼容的涂鸦红外网关，创建遥控器，通过原装实体遥控器学习红外信号，并在局域网中控制设备。

**说明：** 已移除不可靠的 Smart Life 云端按键导入功能。旧功能可能只获取技术名称，而无法获得真正可用的红外信号。二维码登录**仅用于配置红外网关**，并不下载云端遥控器布局或红外码。

<p align="center"><img src="assets/workflow.svg" alt="连接网关、创建遥控器、学习按键、局域网控制" width="100%"></p>

## 功能

- **网关配置：** 使用 Tuya / Smart Life 二维码登录，或手动输入 IP、Device ID、Local Key。
- **遥控器编辑：** 创建、重命名、排序遥控器和按键，并选择设备类别与图标。
- **引导式学习：** 使用实体原装遥控器逐个录制真实红外信号。
- **本地控制：** 通过 Home Assistant 的 `remote.*` 实体发送已保存的命令。
- **高级工具：** 支持兼容的 Flipper `.ir` 文件、手动代码输入及备份。

## 安装

打开 **设置 → Marketplace**（原 **HACS**），搜索 **Tuya IR Studio**，并从目录中安装此集成。

前往 **设置 → 设备与服务 → 添加集成 → Tuya IR Studio** 配置红外网关。随后在侧边栏创建遥控器，添加所需按键，使用**逐步学习**功能。请务必确认实体设备确实响应。

## 限制

本项目不会根据设备类别自动编造按钮，也不会自动导入 Smart Life 的遥控器布局。射频、蓝牙和 HDMI-CEC 不是红外信号。部分空调需要完整状态编码。配置完成后，只要局域网和网关可用，已学习的红外命令可以离线发送；二维码配置可能需要连接 Tuya。

[配置指南（英文）](docs/TUYA_ONBOARDING.md) · [开发计划（英文）](ROADMAP.md) · [更新日志](CHANGELOG.md) · [反馈问题](https://github.com/Joka-kun/tuya-ir-studio/issues)

MIT 许可证。本项目为独立开源项目。