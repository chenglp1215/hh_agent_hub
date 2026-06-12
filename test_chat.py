#!/usr/bin/env python3
"""
Chat API 测试脚本
用法:
    python test_chat.py "<message>"
    python test_chat.py "<message>" --stream
    python test_chat.py "<message>" --app-id 1

URL 和认证信息固化在脚本顶部，可按需修改。
"""

import argparse
import json
import sys
import time
import requests

# ============================================================
# 测试配置 — 按需修改
# ============================================================
BASE_URL = "http://10.5.30.227:9020"
CHAT_URL = f"{BASE_URL}/api/v1/chat"
HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": "ak-VvVxOzYWM8WCFM1E3lXIhZfTwFWa2Y6N",
}
COOKIES = {"auth_token": "test123"}
DEFAULT_APP_ID = 1
TIMEOUT = 300
# ============================================================


TRACE_ICONS = {
    "supervisor_start": "🔄",
    "supervisor_route": "➡️",
    "supervisor_end": "🏁",
    "supervisor_force_end": "🛑",
    "agent_start": "🚀",
    "agent_end": "✅",
}


def print_trace(trace: list):
    """格式化打印执行追踪"""
    if not trace:
        return
    print("📋 执行追踪:")
    print("-" * 50)
    for entry in trace:
        icon = TRACE_ICONS.get(entry.get("type", ""), "•")
        t = entry.get("type", "")
        if t == "supervisor_start":
            print(f"  {icon} Supervisor 第 {entry['round']} 轮调度决策")
        elif t == "supervisor_route":
            print(f"  {icon} 路由到: [{entry['target']}]")
        elif t == "supervisor_end":
            print(f"  {icon} 工作流结束 ({entry.get('reason', '')})")
        elif t == "supervisor_force_end":
            print(f"  {icon} 达到最大轮次限制，强制结束")
        elif t == "agent_start":
            print(f"  {icon} Agent [{entry['agent']}] 开始执行 (输入 {entry['input_len']} chars)")
        elif t == "agent_end":
            print(f"  {icon} Agent [{entry['agent']}] 完成 (输出 {entry['output_len']} chars, 耗时 {entry['elapsed_ms']}ms)")
        else:
            print(f"  {icon} {json.dumps(entry, ensure_ascii=False)}")
    print("-" * 50)


def parse_sse(response):
    """解析 SSE 流式响应"""
    current_event = None
    for line in response.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("event: "):
            current_event = line[7:]
        elif line.startswith("data: "):
            data = json.loads(line[6:])
            yield current_event, data


def test_stream(body: dict):
    """流式测试"""
    print("=" * 60)
    print("  流式 Chat 测试 (SSE)")
    print("=" * 60)
    print(f"Message: {body['message']}")
    print()

    start = time.time()
    response = requests.post(
        CHAT_URL, json=body, headers=HEADERS, cookies=COOKIES,
        stream=True, timeout=TIMEOUT,
    )
    response.raise_for_status()

    for event, data in parse_sse(response):
        ts = f"{time.time() - start:.2f}s"

        if event == "thinking":
            print(f"  [{ts}] 💭 {data.get('content', '')}")
        elif event == "agent_call":
            print(f"  [{ts}] 🔄 调用 [{data.get('agent', '?')}]")
        elif event == "agent_result":
            agent = data.get("agent", "?")
            output = data.get("output", "")
            print(f"  [{ts}] ✅ [{agent}] ({len(output)} chars):")
            print(f"       {output[:300]}{'...' if len(output) > 300 else ''}")
        elif event == "text":
            print(f"  [{ts}] 📝 {data.get('content', '')[:200]}")
        elif event == "done":
            print(f"  [{ts}] ✅ 完成 ({data.get('duration_ms', 0)}ms)")
            print(f"       Session: {data.get('session_id', '')}")
        elif event == "error":
            print(f"  [{ts}] ❌ {data.get('message', '')}")

    print(f"\n总耗时: {time.time() - start:.2f}s")


def test_non_stream(body: dict):
    """非流式测试"""
    print("=" * 60)
    print("  非流式 Chat 测试")
    print("=" * 60)
    print(f"URL:     {CHAT_URL}")
    print(f"App ID:  {body.get('app_id', 'N/A')}")
    print(f"Message: {body['message']}")
    print()

    start = time.time()
    response = requests.post(
        CHAT_URL, json=body, headers=HEADERS, cookies=COOKIES,
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    elapsed = time.time() - start

    result = response.json()
    code = result.get("code")
    if code != 200:
        print(f"❌ API 返回错误 code={code}: {result.get('message', '')}")
        return

    data = result.get("data", {})
    final_answer = data.get("message", "")
    intermediate = data.get("intermediate_results", {})
    duration = data.get("duration_ms", 0)
    trace = data.get("trace", [])

    print(f"💬 最终回复 ({len(final_answer)} chars):")
    print(f"   {final_answer}")
    print()

    # 打印追踪
    print_trace(trace)

    # 打印中间结果
    if intermediate:
        print(f"📊 中间结果 ({len(intermediate)} agents):")
        for agent_name, output in intermediate.items():
            if agent_name.startswith("_"):
                continue  # 跳过内部字段
            output_str = str(output)
            print(f"   [{agent_name}] ({len(output_str)} chars):")
            print(f"   {output_str[:300]}{'...' if len(output_str) > 300 else ''}")
            print()

    print(f"⏱ 总耗时: {elapsed:.2f}s | API 报告: {duration}ms")
    print(f"📋 Session: {data.get('session_id', 'N/A')}")


def main():
    parser = argparse.ArgumentParser(description="Chat API 测试脚本")
    parser.add_argument("message", help="测试消息内容")
    parser.add_argument("--app-id", type=int, default=DEFAULT_APP_ID, help=f"App ID (默认: {DEFAULT_APP_ID})")
    parser.add_argument("--session-id", default=None, help="Session ID (续接会话)")
    parser.add_argument("--stream", action="store_true", help="流式模式 (SSE)")
    parser.add_argument("--url", default=CHAT_URL, help=f"Chat API URL (默认: {CHAT_URL})")
    args = parser.parse_args()

    body = {
        "app_id": args.app_id,
        "message": args.message,
        "stream": args.stream,
    }
    if args.session_id:
        body["session_id"] = args.session_id

    try:
        if args.stream:
            test_stream(body)
        else:
            test_non_stream(body)
    except requests.exceptions.Timeout:
        print(f"❌ 请求超时 ({TIMEOUT}s)")
        sys.exit(1)
    except requests.exceptions.ConnectionError as e:
        print(f"❌ 连接失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 异常: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
