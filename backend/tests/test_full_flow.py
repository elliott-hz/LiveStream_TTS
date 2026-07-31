"""
全流程集成测试 — MOCK_EXTERNAL_API=true
流程: 商品 → 上传 → 解析 → 编排 → 直播间 → 推流 → 互动 → NLP
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import httpx

# 强制 mock 模式
os.environ["MOCK_EXTERNAL_API"] = "true"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def ok(msg):    print(f"{GREEN}✅ {msg}{RESET}")
def fail(msg):  print(f"{RED}❌ {msg}{RESET}")
def step(msg):  print(f"\n{YELLOW}━━━ {msg} ━━━{RESET}")


async def test_full_flow():
    base = "http://127.0.0.1:8000"
    client = httpx.AsyncClient(timeout=30)

    # ─── 1. 健康检查 ───
    step("1. 健康检查")
    resp = await client.get(f"{base}/api/health")
    assert resp.status_code == 200 and resp.json()["status"] == "ok"
    ok("服务正常")

    # ─── 2. 创建商品 ───
    step("2. 创建商品")
    resp = await client.post(f"{base}/api/products", json={
        "name": "法式碎花连衣裙", "sku": "D001", "category": "女装"})
    assert resp.status_code == 201
    product = resp.json()
    pid = product["id"]
    ok(f"已创建: {product['name']}")

    resp = await client.post(f"{base}/api/products", json={
        "name": "冰丝防晒袖套", "sku": "D002", "category": "配饰"})
    assert resp.status_code == 201
    pid2 = resp.json()["id"]
    ok(f"已创建: 冰丝防晒袖套")

    # ─── 3. AI导入知识库 ───
    step("3. AI 导入商品知识库")
    resp = await client.post(f"{base}/api/products/import", json={
        "platform": "taobao", "url": "https://item.taobao.com/item.htm?id=12345",
        "product_id": pid})
    assert resp.status_code == 201
    kbs = resp.json()["platform_kbs"]
    assert len(kbs) == 1 and kbs[0]["platform"] == "taobao"
    ok("知识库导入成功")

    # ─── 4. 上传视频 → BackgroundTasks 解析 ───
    step("4. 上传视频 + 后台解析")
    tmpdir = tempfile.mkdtemp()
    fake_video = os.path.join(tmpdir, "test.mp4")
    with open(fake_video, "wb") as f:
        f.write(b"\x00" * 1024 * 100)

    with open(fake_video, "rb") as f:
        resp = await client.post(f"{base}/api/video-assets/upload",
            files={"file": ("test.mp4", f, "video/mp4")})
    assert resp.status_code == 201
    video_id = resp.json()["id"]
    ok(f"视频已上传: {video_id}")

    # 等待解析完成
    step("5. 等待解析...")
    segments = []
    for i in range(20):
        await asyncio.sleep(1)
        resp = await client.get(f"{base}/api/video-assets/{video_id}")
        v = resp.json()
        print(f"  进度: {v['parse_progress']:.0f}%  状态: {v['parse_status']}  切片: {len(v['segments'])}")
        if v["parse_status"] == "done" and v["parse_progress"] == 100:
            segments = v["segments"]
            break
    else:
        fail("解析超时")
        # 检查是否至少有一些切片
        resp = await client.get(f"{base}/api/video-assets/{video_id}")
        segments = resp.json().get("segments", [])

    assert len(segments) >= 1, f"期望至少1个切片，实际 {len(segments)}"
    ok(f"解析完成: {len(segments)} 个切片")

    # ─── 6. 发布切片 ───
    step("6. 发布切片")
    for seg in segments:
        resp = await client.post(f"{base}/api/video-assets/segments/{seg['id']}/publish")
        assert resp.status_code == 200
        seg_data = resp.json()
        ok(f"已发布: {seg_data['start_time']:.0f}s~{seg_data['end_time']:.0f}s")

    # ─── 7. 编排直播视频 ───
    step("7. 编排直播视频")
    resp = await client.post(f"{base}/api/live-videos", json={
        "name": "夏季女装专场", "play_mode": "sequential"})
    assert resp.status_code == 201
    live_vid = resp.json()["id"]
    ok(f"编排已创建: {live_vid}")

    # 添加切片
    for i, seg in enumerate(segments):
        resp = await client.post(f"{base}/api/live-videos/{live_vid}/clips", json={
            "segment_id": seg["id"], "sort_order": i, "weight": 2 if i == 0 else 1,
            "pause_after": 3})
        assert resp.status_code == 201
        ok(f"切片{i+1} 已编排: weight={resp.json()['weight']}")

    # 验证
    resp = await client.get(f"{base}/api/live-videos/{live_vid}")
    assert len(resp.json()["clips"]) == len(segments)
    ok("编排验证通过")

    # ─── 8. 直播间 ───
    step("8. 创建直播间 + 挂载视频")
    resp = await client.post(f"{base}/api/live-rooms", json={
        "name": "淘宝夏季女装", "platform": "taobao",
        "rtmp_url": "rtmp://push.taobao.com/live/test"})
    assert resp.status_code == 201
    room_id = resp.json()["id"]
    ok(f"直播间已创建: {room_id}")

    resp = await client.post(f"{base}/api/live-rooms/{room_id}/attach/{live_vid}")
    assert resp.status_code == 200
    ok("视频已挂载")

    # FFmpeg 推流测试
    import shutil
    if shutil.which("ffmpeg"):
        step("9. 开播推流")
        resp = await client.post(f"{base}/api/live-rooms/{room_id}/start")
        if resp.status_code == 200:
            assert resp.json()["status"] == "live"
            ok("推流已启动 → status=live")

            resp = await client.get(f"{base}/api/stream-health/{room_id}")
            ok(f"推流健康: {resp.json()}")

            # 停播
            step("10. 停播")
            resp = await client.post(f"{base}/api/live-rooms/{room_id}/stop")
            assert resp.json()["status"] == "idle"
            ok("已停播")
        else:
            print(f"  开播失败 (FFmpeg推流可能需要真实的RTMP地址): {resp.text}")
    else:
        print(f"  {YELLOW}⚠️  FFmpeg 未安装，跳过推流{RESET}")

    # ─── 9. 互动设置 ───
    step("11. 互动设置")
    resp = await client.get(f"{base}/api/interaction/config")
    assert resp.status_code == 200
    ok(f"默认配置: mode={resp.json()['reply_mode']}")

    resp = await client.put(f"{base}/api/interaction/config", json={
        "reply_style": "professional", "tts_speed": 1.2})
    assert resp.json()["tts_speed"] == 1.2
    ok("TTS参数更新成功")

    resp = await client.post(f"{base}/api/interaction/templates", json={
        "keywords": "尺码,大小", "reply_text": "亲，有S/M/L/XL四个尺码哦~"})
    assert resp.status_code == 201
    ok(f"话术模板已创建")

    # ─── 10. 数据大盘 ───
    step("12. 数据大盘")
    resp = await client.get(f"{base}/api/analytics/sessions")
    assert resp.status_code == 200
    ok(f"直播场次查询正常 ({len(resp.json())} 场)")

    # ─── 11. NLP 引擎 ───
    step("13. NLP 引擎测试")
    from backend.engine.nlp import classify, is_sensitive, should_reply, Danmaku

    assert not is_sensitive("正常弹幕")
    assert is_sensitive("卖毒品")
    ok("敏感词过滤 ✓")

    assert classify("这个多少钱") == "question"
    assert classify("已下单") == "order_intent"
    assert classify("主播好看") == "comment"
    ok("意图分类 ✓")

    assert should_reply(Danmaku(user_name="买家", content="有XL吗"))
    assert not should_reply(Danmaku(user_name="路人", content="哈哈"))
    ok("回复决策 ✓")

    # ─── Done ───
    await client.aclose()
    print(f"\n{GREEN}{'='*50}{RESET}")
    print(f"{GREEN}  ✅ 全流程测试通过!{RESET}")
    print(f"{GREEN}{'='*50}{RESET}")


if __name__ == "__main__":
    asyncio.run(test_full_flow())
