# 🛡️ Prompt-Sentinel

<!-- 徽章区 (Badges) - 直接复制即可显示 -->
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30%2B-FF4B4B?logo=streamlit&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-Supported-black?logo=ollama&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-Development-orange)

> **A lightweight and interactive Prompt Injection defense gateway for LLM Agents.**
> 一个面向 LLM Agent 的 Prompt 注入防御与可视化审计系统。

## 📖 项目简介 (Introduction)

随着大语言模型（LLM）和智能体（Agent）的普及，**提示词注入（Prompt Injection）**和**越狱攻击（Jailbreak）**成为了最大的安全隐患。`Prompt-Sentinel` 旨在提供一个轻量级、即插即用的安全网关，在用户输入与底层大模型（如 DeepSeek、Ollama）之间建立一道坚固的防线。

本项目不仅提供实时的攻击拦截，还配备了直观的**安全审计看板**，将黑盒的模型交互过程变得可追踪、可审计，是研究 LLM 对抗鲁棒性的绝佳可视化实验平台。

## ✨ 核心特性 (Features)

- **🛡️ 双引擎检测机制**：结合正则表达式（Regex）快速匹配与语义向量相似度计算，实现纵深防御。
- **📊 实时可视化审计**：基于 Streamlit 构建，左侧实时对话，右侧动态展示拦截日志与威胁统计。
- **🔌 多模型无缝兼容**：轻松接入本地开源模型（Ollama）或云端商业 API（DeepSeek）。
- **⚙️ 配置外部化**：安全策略与敏感词库通过 `config.yaml` 管理，实现代码与规则解耦。

## 🏗️ 系统架构 (Architecture)

```text
[ 用户输入 ]
     │
     ▼
[ Streamlit UI 层 ]
     │
     ▼
[ 安全网关控制层 ] ──(判定为攻击)──> [ 拦截警告 & 写入审计日志 ]
     │
(判定为安全)
     ▼
[ 规则/语义检测引擎 (Regex / NLP) ]
     │
     ▼
[ 大模型代理层 (DeepSeek / Ollama) ]



