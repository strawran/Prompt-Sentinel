"""Streamlit demo and metadata-only audit dashboard."""

from __future__ import annotations

import os

import httpx
import pandas as pd
import streamlit as st


API_URL = os.getenv("PROMPT_SENTINEL_API_URL", "http://127.0.0.1:8000").rstrip("/")
AUDIT_TOKEN = os.getenv("PROMPT_SENTINEL_AUDIT_TOKEN", "")

st.set_page_config(page_title="Prompt-Sentinel", layout="wide")
st.title("Prompt-Sentinel")


def api_request(method: str, path: str, **kwargs) -> dict | None:
    try:
        with httpx.Client(timeout=90) as client:
            response = client.request(method, f"{API_URL}{path}", **kwargs)
        if response.is_error:
            error = response.json()
            st.error(
                f"Gateway HTTP {response.status_code}: "
                f"{error.get('detail') or error.get('error') or response.text}"
            )
            return None
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        st.error(f"无法连接网关：{exc}")
        return None


inspect_tab, chat_tab, audit_tab = st.tabs(["内容检测", "模型调用", "审计记录"])

with inspect_tab:
    role = st.radio("内容来源", ["tool", "user"], horizontal=True)
    text = st.text_area("待检查文本", height=180, placeholder="粘贴网页、检索结果或用户消息")
    if st.button("检测", disabled=not text.strip()):
        result = api_request("POST", "/inspect", json={"text": text, "role": role})
        if result:
            (st.error if result["action"] == "block" else st.success)(
                "已拦截" if result["action"] == "block" else "允许通过"
            )
            st.json(result)

with chat_tab:
    prompt = st.text_area("发送给模型的用户消息", height=130, key="chat_prompt")
    if st.button("通过网关发送", disabled=not prompt.strip()):
        result = api_request(
            "POST",
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": prompt}], "stream": False},
        )
        if result:
            try:
                st.write(result["choices"][0]["message"]["content"])
            except (KeyError, IndexError, TypeError):
                st.json(result)

with audit_tab:
    if st.button("刷新审计记录"):
        st.rerun()
    headers = {"X-Audit-Token": AUDIT_TOKEN} if AUDIT_TOKEN else {}
    result = api_request("GET", "/audit?limit=200", headers=headers)
    if result:
        counts = result["counts"]
        columns = st.columns(3)
        columns[0].metric("允许", counts.get("allow", 0))
        columns[1].metric("拦截", counts.get("block", 0))
        columns[2].metric("检测错误", counts.get("error", 0))
        events = result["events"]
        if events:
            frame = pd.DataFrame(events)
            st.subheader("判定分布")
            st.bar_chart(frame["action"].value_counts())
            st.subheader("规则命中")
            rule_counts = frame.explode("rule_ids")["rule_ids"].dropna().value_counts()
            if not rule_counts.empty:
                st.bar_chart(rule_counts)
            else:
                st.info("暂无规则命中")
            st.dataframe(
                frame[[
                    "created_at", "request_id", "source", "role", "action",
                    "engines", "rule_ids", "similarity", "char_count"
                ]],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("暂无审计记录")
