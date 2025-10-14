from typing import List, Dict, Any
import json
import re
import time
import base64

from load_llm import get_llm_for_opinions

ASPECT_KEYWORDS = {
    "wifi","internet","clean","cleanliness","noise","quiet","location","transport","metro","ubahn","s-bahn","subway","host","responsive","check-in","checkin","price","value","bed","bathroom","kitchen","heating","ac","aircon","view","safety","neighborhood","neighbourhood","space","spacious","comfortable","soundproof","tram","bus"
}

GENERIC_BLACKLIST = {
    "great place","great location","nice place","nice location","amazing place","amazing location",
    "highly recommend","would stay again","stay again","recommend",
    "die wohnung","wohnung","schone wohnung","schöne wohnung"
}

ASCII_RE = re.compile(r"^[ -~]+$")
WORD_RE = re.compile(r"[a-zA-Z]+")
SENTENCE_END_RE = re.compile(r"[\.!?]\s*$")
VERB_HINTS = {
    "is","are","was","were","has","have","includes","offers","provides","feels","seems","sounds",
    "works","runs","located","close","near","kept","cleaned","heated","cooled","quiet","noisy"
}

# 目标 token 预算（估算），用于控制 prompt 长度
_PROMPT_TOKEN_BUDGET = 6000
_RETRY_TOKEN_BUDGET = 3500


# -------------------------------
# helpers (text utils)
# -------------------------------


def _truncate_comments(comments: List[str], max_comments: int = 1000, max_chars_per_comment: int = 300) -> List[str]:
    result: List[str] = []
    for c in comments[:max_comments]:
        c = (c or "").strip()
        if not c:
            continue
        if len(c) > max_chars_per_comment:
            c = c[:max_chars_per_comment]
        result.append(c)
    return result


def _strip_code_fences(text: str) -> str:
    if not text:
        return ""
    t = text
    # 去除三引号代码块（包括```json 标记）
    t = re.sub(r"```\s*json", "", t, flags=re.IGNORECASE)
    t = t.replace("```", "")
    return t.strip()


def _safe_json_extract(text: str) -> Dict[str, Any]:
    # 先清理代码框
    text = _strip_code_fences(text)
    try:
        return json.loads(text)
    except Exception as e:
        # 尝试截取第一个 JSON 片段
        m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if m:
            return json.loads(m.group(1))
        raise ValueError(f"LLM output is not valid JSON: {str(e)}")


def _salvage_items_from_text(text: str, top_n: int) -> List[Dict[str, Any]]:
    """宽松解析：从 LLM 文本中尽可能抽取 {text, count, comments[]} 项。
    - 去除代码框
    - 提取所有出现的 "text": "..." 片段
    - 就近解析 count 与 comments 数组（可选）
    - 通过 _is_aspect_phrase 与 _is_complete_opinion 校验
    """
    if not text:
        return []
    raw = _strip_code_fences(text)
    items: List[Dict[str, Any]] = []
    seen = set()

    # 查找 "text": "..." 片段
    for m in re.finditer(r'"text"\s*:\s*"([\s\S]*?)"', raw):
        txt = m.group(1).strip()
        if not txt or txt.lower() in seen:
            continue
        # 限制长度，防止异常长文本
        if len(txt) > 300:
            txt = txt[:300].rstrip()
        # 在接下来的一小段文本范围内查找 count / comments
        tail = raw[m.end(): m.end() + 1200]
        count_val = 0
        mc = re.search(r'"count"\s*:\s*(\d+)', tail)
        if mc:
            try:
                count_val = int(mc.group(1))
            except Exception:
                count_val = 0
        comments_list: List[str] = []
        mm = re.search(r'"comments"\s*:\s*\[(.*?)\]', tail, flags=re.DOTALL)
        if mm:
            # 解析数组里的字符串
            arr = mm.group(1)
            for sm in re.finditer(r'"([\s\S]*?)"', arr):
                s = (sm.group(1) or "").strip()
                if s:
                    if len(s) > 180:
                        s = s[:180]
                    comments_list.append(s)
                if len(comments_list) >= 3:
                    break

        # 过滤与规范化
        if _is_aspect_phrase(txt) and _is_complete_opinion(txt):
            seen.add(txt.lower())
            items.append({"text": txt, "count": count_val, "comments": comments_list})
        if len(items) >= max(1, int(top_n) * 2):
            break

    # 剪裁到 top_n，按 count 排序
    if items:
        items = sorted(items, key=lambda x: x.get("count", 0), reverse=True)[: max(1, int(top_n))]
    return items


def _is_aspect_phrase(text: str) -> bool:
    t = text.lower().strip()
    if not t or t in GENERIC_BLACKLIST:
        return False
    if not ASCII_RE.match(t):
        return False
    tokens = set(WORD_RE.findall(t))
    return any(k in tokens for k in ASPECT_KEYWORDS)


def _is_complete_opinion(text: str) -> bool:
    t = (text or "").strip()
    words = WORD_RE.findall(t)
    if len(words) < 5 or len(words) > 20:
        return False
    tokens = set(w.lower() for w in words)
    if not any(v in tokens for v in VERB_HINTS):
        return False
    if not SENTENCE_END_RE.search(t):
        return False
    return True


def _estimate_tokens(text: str) -> int:
    """粗略估算 token 数：英文平均约 4 字符/Token，中文约 2-3；这里保守取 4。"""
    if not text:
        return 0
    # 按字符长度估算，加入 5% 余量
    return int(len(text) / 4 * 1.05) + 1


def _build_prompt_with_budget(instruction: str, comments: List[str], token_budget: int) -> Dict[str, Any]:
    header = instruction + "\n\nReviews:\n"
    used_lines = 0
    body_acc = []
    # 预估 header token
    est = _estimate_tokens(header)
    for c in comments:
        line = f"- {c}\n"
        cand = header + ("".join(body_acc)) + line
        cand_tokens = _estimate_tokens(cand)
        if cand_tokens > token_budget:
            break
        body_acc.append(line)
        used_lines += 1
        est = cand_tokens
    prompt = header + ("".join(body_acc))
    return {"prompt": prompt, "used": used_lines, "est_tokens": est, "chars": len(prompt)}


def _extract_text_from_ai_message(resp: Any) -> str:
    """尽可能从 AIMessage 中提取文本内容（兼容 Gemini 的 candidates/parts 结构，包括 inline_data JSON）。"""
    try:
        txt = getattr(resp, "content", None)
        if isinstance(txt, str) and txt.strip():
            return txt
        # 其他原始元数据位置
        ak = getattr(resp, "additional_kwargs", {}) or {}
        rm = getattr(resp, "response_metadata", {}) or {}
        if ak:
            try:
                print(f"🧠 [opinions] additional_kwargs_keys= {list(ak.keys())[:10]}")
            except Exception:
                pass
        if rm:
            try:
                print(f"🧠 [opinions] response_metadata_keys= {list(rm.keys())[:10]}")
            except Exception:
                pass
        # 可能的安全提示
        pf = (ak.get("promptFeedback") or ak.get("prompt_feedback") or rm.get("promptFeedback") or rm.get("prompt_feedback"))
        if pf:
            try:
                print(f"⚠️ [opinions] prompt_feedback={json.dumps(pf, ensure_ascii=False)[:400]}")
            except Exception:
                pass
        # 不同层级候选结构
        candidates = ak.get("candidates") or rm.get("candidates") or []
        # 某些封装在 response 下
        if not candidates:
            resp_obj = ak.get("response") or rm.get("response")
            if isinstance(resp_obj, dict):
                candidates = resp_obj.get("candidates") or []
        # 遍历候选，提取 text 或 inline_data(JSON)
        for cand in candidates:
            # 先 content.parts
            content_obj = cand.get("content") or {}
            parts = content_obj.get("parts") if isinstance(content_obj, dict) else None
            if parts and isinstance(parts, list):
                for p in parts:
                    if isinstance(p, dict):
                        t = p.get("text")
                        if isinstance(t, str) and t.strip():
                            return t
                        inline_data = p.get("inline_data") or p.get("inlineData")
                        if isinstance(inline_data, dict):
                            mime = inline_data.get("mime_type") or inline_data.get("mimeType")
                            data_b64 = inline_data.get("data")
                            if mime and "json" in str(mime).lower() and isinstance(data_b64, str) and data_b64:
                                try:
                                    decoded = base64.b64decode(data_b64).decode("utf-8", errors="ignore")
                                    if decoded.strip():
                                        return decoded
                                except Exception:
                                    pass
            # 旧风格：content 为列表
            if isinstance(content_obj, list):
                for part in content_obj:
                    if isinstance(part, dict):
                        t = part.get("text")
                        if isinstance(t, str) and t.strip():
                            return t
                        inline_data = part.get("inline_data") or part.get("inlineData")
                        if isinstance(inline_data, dict):
                            mime = inline_data.get("mime_type") or inline_data.get("mimeType")
                            data_b64 = inline_data.get("data")
                            if mime and "json" in str(mime).lower() and isinstance(data_b64, str) and data_b64:
                                try:
                                    decoded = base64.b64decode(data_b64).decode("utf-8", errors="ignore")
                                    if decoded.strip():
                                        return decoded
                                except Exception:
                                    pass
            # message.content[0].text 兜底
            msg = cand.get("message") or {}
            cont = msg.get("content")
            if isinstance(cont, list) and cont:
                t = cont[0].get("text") if isinstance(cont[0], dict) else None
                if isinstance(t, str) and t.strip():
                    return t
    except Exception as _e:
        # 忽略解析异常，返回空
        pass
    return ""


# -------------------------------
# main API (conversational_chat style)
# -------------------------------


def extract_review_opinions(
    comments: List[str],
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    """
    用 LLM 从 Airbnb 评论中抽取英文观点短句（短句必须包含主谓并以标点结尾），并返回证据片段：
    [{ text, count, comments[] }]
    - 仅使用 LLM；若失败，抛出异常（不在此处兜底）。
    """
    print("🧠 [opinions] start extract_review_opinions, top_n=", top_n)
    if not comments:
        raise ValueError("No comments provided for opinion extraction")

    truncated = _truncate_comments(comments)
    print(f"🧠 [opinions] comments_in={len(comments)}, truncated={len(truncated)}")
    # minimal logs only

    example = {
        "items": [
            {
                "text": "The Wi‑Fi is fast and reliable.",
                "count": 42,
                "comments": [
                    "WiFi was fast for streaming Netflix.",
                    "Internet was stable throughout our stay."
                ]
            },
            {
                "text": "The apartment is close to the metro.",
                "count": 37,
                "comments": [
                    "U-bahn is just 3 minutes away.",
                    "Close to the station, easy to get around."
                ]
            }
        ]
    }

    instruction = f"""
You will analyze guest review comments for Airbnb listings in Berlin.
Write up to {top_n} concise English opinion sentences about the listings. Each item must:
- be a short complete sentence (subject + verb), end with a period.
- state an aspect + stance (e.g., Wi‑Fi speed, cleanliness, noise at night, proximity to metro, host responsiveness, price/value, check‑in, comfort, heating/AC, kitchen, safety).
- be English only (translate if needed), no non-English words.
- avoid generic compliments or fragments; do not output tags like "great place".
- deduplicate paraphrases; output one canonical sentence per idea.
Include an approximate supporting count for each sentence.
Return ONLY valid JSON with this exact schema and nothing else. Example:\n{json.dumps(example)}
""".strip()

    # 动态控制 prompt 长度（按 token 预算裁剪评论行数）
    built = _build_prompt_with_budget(instruction, truncated, _PROMPT_TOKEN_BUDGET)
    prompt = built["prompt"]
    print(f"🧠 [opinions] prompt_chars={built['chars']}, est_tokens={built['est_tokens']}, used_comments={built['used']}")

    print("🧠 [opinions] invoking LLM ...")
    llm = get_llm_for_opinions()
    t0 = time.time()
    resp = llm.invoke(prompt)
    print(f"🧠 [opinions] resp={resp}")
    latency = time.time() - t0
    rm = getattr(resp, "response_metadata", {}) if resp is not None else {}
    um = getattr(resp, "usage_metadata", {}) if resp is not None else {}
    print(f"⏱️ [opinions] llm_latency_sec={latency:.2f}, finish={rm.get('finish_reason')}, in_toks={um.get('input_tokens')}, out_toks={um.get('output_tokens')}")

    content = getattr(resp, "content", "") if resp is not None else ""
    if not content:
        # Fallback: 从 additional_kwargs 中提取文本，记录安全/阻断原因（精简日志）
        try:
            ak = getattr(resp, "additional_kwargs", {}) if resp is not None else {}
            rm = getattr(resp, "response_metadata", {}) if resp is not None else {}
            pf = (ak.get("promptFeedback") or ak.get("prompt_feedback") or rm.get("promptFeedback") or rm.get("prompt_feedback"))
            if pf:
                try:
                    print(f"⚠️ [opinions] prompt_feedback={json.dumps(pf, ensure_ascii=False)[:300]}")
                except Exception:
                    pass
            extracted = _extract_text_from_ai_message(resp)
            if extracted and isinstance(extracted, str):
                content = extracted
        except Exception:
            content = content or ""

    print(f"🧠 [opinions] resp_content_len={len(content)}")
    try:
        preview_head = (content[:800] + ("…" if len(content) > 800 else ""))
        print(f"🧠 [opinions] resp_preview_head=\n{preview_head}")
    except Exception:
        pass

    # 若依然为空，进行一次轻量重试：减少样本量并使用消息形式调用
    if not content:
        try:
            print("⚠️ [opinions] empty content, retrying with fewer samples and message API ...")
            built2 = _build_prompt_with_budget(instruction, truncated, _RETRY_TOKEN_BUDGET)
            prompt2 = built2["prompt"]
            print(f"🧠 [opinions] retry_prompt_chars={built2['chars']}, retry_est_tokens={built2['est_tokens']}, retry_used_comments={built2['used']}")
            from langchain_core.messages import HumanMessage
            t1 = time.time()
            resp2 = llm.invoke([HumanMessage(content=prompt2)])
            print(f"⏱️ [opinions] retry_latency_sec={time.time() - t1:.2f}")
            content = getattr(resp2, "content", "") or _extract_text_from_ai_message(resp2) or ""
            print(f"🧠 [opinions] retry_resp_len={len(content)}")
            # no verbose preview
        except Exception as e:
            print(f"❌ [opinions] retry_error: {e}")

    if not content:
        raise RuntimeError("Empty response from LLM")

    try:
        data = _safe_json_extract(content)
        print("✅ [opinions] json_parse=ok")
    except Exception as e:
        print(f"❌ [opinions] json_parse_error: {e}")
        # 容错：尝试从文本中抢救部分 items
        try:
            salvaged = _salvage_items_from_text(content, top_n)
        except Exception:
            salvaged = []
        if salvaged:
            print(f"🛟 [opinions] salvage_ok items={len(salvaged)} (tolerant parse)")
            data = {"items": salvaged}
        else:
            # 抛错上层处理
            raise

    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError("LLM JSON missing 'items' array")

    print(f"🧠 [opinions] raw_items={len(items)}")
    normalized: List[Dict[str, Any]] = []
    seen = set()
    for it in items:
        if not isinstance(it, dict):
            continue
        text = str(it.get("text") or "").strip()
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        try:
            count = int(it.get("count") or 0)
        except Exception:
            count = 0
        if not (_is_aspect_phrase(text) and _is_complete_opinion(text)):
            continue
        raw_cmts = it.get("comments")
        cmts: List[str] = []
        if isinstance(raw_cmts, list):
            for c in raw_cmts[:3]:
                s = str(c).strip()
                if s:
                    if len(s) > 180:
                        s = s[:180]
                    cmts.append(s)
        normalized.append({"text": text, "count": count, "comments": cmts})

    # 排序与裁剪
    before_clip = len(normalized)
    normalized = sorted(normalized, key=lambda x: x.get("count", 0), reverse=True)[: max(1, int(top_n))]
    print(f"🧠 [opinions] normalized_items_before_clip={before_clip}, after_clip={len(normalized)}")
    # no top item preview

    if not normalized:
        # 明确抛错，交由上层决定如何处理
        raise ValueError("LLM returned no valid opinion sentences after validation")

    return normalized 