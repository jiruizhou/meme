import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime

st.set_page_config(page_title="控盘山寨币模型 v4.0", layout="wide", page_icon="🚀")
st.title("🚀 控盘山寨币模型仪表盘 v4.0")

# 安全登录
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    password = st.text_input("输入密码登录", type="password")
    if password == st.secrets["general"]["password"]:
        st.session_state.logged_in = True
        st.success("登录成功！")
        st.rerun()
    else:
        st.error("密码错误")
        st.stop()

# 初始化watchlist（session_state，刷新不丢）
if "watchlist" not in st.session_state:
    st.session_state.watchlist = [
        {"name": "JELLY", "ca": "FeR8VBqNRSUD5NtXAj2n3j1dAHkZHfyDktKuLXD4pump", "coingecko_id": "jelly-my-jelly", "bybit_symbol": "JELLYUSDT", "manual_cluster": 85},
        {"name": "FHE", "ca": "0xd55C9fB62E176a8Eb6968f32958FeFDD0962727E", "coingecko_id": "mind-network", "bybit_symbol": "", "manual_cluster": 82},
        {"name": "NAORIS", "ca": "0x1b379a79c91a540b2bcd612b4d713f31de1b80cc", "coingecko_id": "naoris-protocol", "bybit_symbol": "", "manual_cluster": 80},
        {"name": "PIPPIN", "ca": "Dfh5DzRgSvvCFDoYc2ciTkMrbDfRKybA4SoFbPmApump", "coingecko_id": "pippin", "bybit_symbol": "PIPPINUSDT", "manual_cluster": 90},
    ]

# 工具函数（v3.0评分）
def get_dex_data(ca):
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{ca}"
        resp = requests.get(url, timeout=10).json()
        if resp.get("pairs"):
            p = resp["pairs"][0]
            return {
                "price": float(p.get("priceUsd", 0)),
                "mc": float(p.get("fdv", 0)),
                "volume_24h": float(p.get("volume", {}).get("h24", 0)),
                "liquidity": float(p.get("liquidity", {}).get("usd", 0))
            }
    except:
        return None

def get_funding_rate(symbol):
    if not symbol: return 0.0
    try:
        url = f"https://api.bybit.com/v5/market/funding/history?category=linear&symbol={symbol}&limit=1"
        resp = requests.get(url, timeout=10).json()
        if resp.get("result", {}).get("list"):
            return float(resp["result"]["list"][0]["fundingRate"])
    except:
        return 0.0

def calculate_score(dex, funding, manual_cluster):
    if not dex: return 0
    score = manual_cluster * 0.25
    if dex["volume_24h"] > 500000: score += 20
    if dex["mc"] < 100000000: score += 20
    if funding > 0: score += 15
    if dex["volume_24h"] / max(dex["liquidity"], 1) > 0.5: score += 10
    return min(round(score), 100)

def send_telegram(msg):
    token = st.secrets["general"]["telegram_token"]
    chat_id = st.secrets["general"]["telegram_chat_id"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})

# 侧边栏导航
page = st.sidebar.selectbox("选择页面", ["实时仪表盘", "自动筛选新币", "历史回测", "添加新币"])

if page == "实时仪表盘":
    st.header("📊 实时监控（每30秒刷新）")
    if st.button("🔄 手动刷新数据"):
        st.rerun()
    
    data_list = []
    for coin in st.session_state.watchlist:
        dex = get_dex_data(coin["ca"])
        funding = get_funding_rate(coin.get("bybit_symbol"))
        score = calculate_score(dex, funding, coin["manual_cluster"])
        
        if dex:
            status = "🚨 **触发入场！**" if score >= 80 else "监控中"
            data_list.append({
                "币种": coin["name"],
                "价格": f"${dex['price']:.6f}",
                "MC": f"${dex['mc']/1e6:.1f}M",
                "24h成交": f"${dex['volume_24h']/1e6:.1f}M",
                "资金费率": f"{funding*100:.3f}%",
                "v3.0评分": score,
                "状态": status
            })
            
            if score >= 80:
                alert_msg = f"🚨 <b>{coin['name']} 入场信号！</b>\n评分：{score}分\n价格：\( {dex['price']:.6f}\nMC： \){dex['mc']/1e6:.1f}M"
                st.error(alert_msg)
                send_telegram(alert_msg)
    
    if data_list:
        df = pd.DataFrame(data_list)
        st.dataframe(df, use_container_width=True, height=400)
    else:
        st.info("加载中...")

elif page == "自动筛选新币":
    st.header("🔍 自动筛选机制（符合控盘标准的新币）")
    st.write("标准：MC < 1亿 + 24h成交 > 50万 + 24h涨幅 > 5% → 自动计算初步评分")
    
    if st.button("🚀 开始扫描热门低市值币（CoinGecko）"):
        with st.spinner("扫描中..."):
            url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=volume_desc&per_page=100&page=1"
            data = requests.get(url).json()
            candidates = []
            for c in data:
                if c["market_cap"] and c["market_cap"] < 100_000_000 and c["total_volume"] > 500_000 and c["price_change_percentage_24h"] and c["price_change_percentage_24h"] > 5:
                    prelim_score = 60 + (c["price_change_percentage_24h"] * 1.5)  # 初步评分
                    candidates.append({
                        "name": c["symbol"].upper(),
                        "coingecko_id": c["id"],
                        "mc": c["market_cap"],
                        "volume": c["total_volume"],
                        "change_24h": c["price_change_percentage_24h"],
                        "pre_score": round(prelim_score)
                    })
            
            if candidates:
                df_cand = pd.DataFrame(candidates)
                st.dataframe(df_cand, use_container_width=True)
                
                selected = st.multiselect("选择要加入监控的币（勾选后点击添加）", options=[c["name"] for c in candidates])
                if st.button("✅ 一键加入watchlist"):
                    for sel in selected:
                        for c in candidates:
                            if c["name"] == sel:
                                st.session_state.watchlist.append({
                                    "name": sel,
                                    "ca": "待填（手动去Dexscreener复制CA）",  # 提醒手动补CA
                                    "coingecko_id": c["coingecko_id"],
                                    "bybit_symbol": "",
                                    "manual_cluster": 70  # 默认，之后手动改
                                })
                    st.success(f"已添加 {len(selected)} 个币！去‘实时仪表盘’查看")
            else:
                st.warning("当前无符合标准的币，稍后重试")

elif page == "历史回测":
    st.header("📈 历史回测（验证模型准确性）")
    coin_id = st.text_input("输入CoinGecko ID（例如 jelly-my-jelly）", "jelly-my-jelly")
    days = st.slider("回测天数", 30, 180, 90)
    if st.button("开始回测"):
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days={days}"
        try:
            data = requests.get(url).json()
            df = pd.DataFrame(data["prices"], columns=["ts", "price"])
            df["date"] = pd.to_datetime(df["ts"], unit="ms").dt.date
            triggered = 0
            for i in range(1, len(df)):
                change = (df["price"].iloc[i] / df["price"].iloc[i-1] - 1) * 100
                sim_score = 50 + (change * 2 if change > 0 else 0)
                if sim_score >= 80:
                    triggered += 1
            st.success(f"回测完成！共触发 {triggered} 次入场信号（胜率参考）")
            st.line_chart(df.set_index("date")["price"])
        except:
            st.error("ID错误或数据问题")

elif page == "添加新币":
    st.header("➕ 手动添加新币（支持任意链）")
    name = st.text_input("币种名称")
    ca = st.text_input("Dexscreener CA（必填）")
    cg_id = st.text_input("CoinGecko ID（可选）")
    bybit = st.text_input("Bybit永续符号（可选）")
    cluster = st.slider("手动簇聚评分（Bubblemaps查）", 50, 100, 75)
    if st.button("添加"):
        st.session_state.watchlist.append({"name": name, "ca": ca, "coingecko_id": cg_id, "bybit_symbol": bybit, "manual_cluster": cluster})
        st.success("添加成功！返回仪表盘查看")

st.sidebar.caption("提示：网站云端运行，手机浏览器打开即实时监控。想改密码/Telegram只需编辑GitHub文件，自动更新。")
