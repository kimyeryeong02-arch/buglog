# -*- coding: utf-8 -*-
"""
곤충 탐험 시연 (최종)
- 스팟 5곳: 병원/정문/첨단바이오연구센터(S20)/도서관/스타벅스 충북대점
- 지도 클릭으로 현재 위치 지정 + 실시간 위치 추적(geolocation → JS 대체)
- 낮/밤(06:00~17:59 / 18:00~05:59) 랜덤 곤충 등장
- 사용자 이미지/설명 적용, 도감 기록
"""

import math
import random
from datetime import datetime
import sys
import streamlit as st
from streamlit_folium import st_folium
import folium
from PIL import Image
from io import BytesIO
from pathlib import Path

# ✅ 등장 횟수 및 스팟 배정 초기화 함수
def reset_appearance_counts():
    st.session_state.insect_counts = {}
    st.session_state.spot_insect = {}
    st.toast("🔄 등장 횟수 초기화 완료!", icon="✨")

# ── 실시간 자동 새로고침
try:
    from streamlit_autorefresh import st_autorefresh
    AUTO_OK = True
except Exception:
    AUTO_OK = False

# ── 1차: streamlit-geolocation
try:
    from streamlit_geolocation import st_geolocation
    GEO_OK = True
except Exception:
    GEO_OK = False

# ── 2차 대체: JS 기반 수신
try:
    from streamlit_js_eval import get_geolocation as js_get_geolocation
    JS_OK = True
except Exception:
    JS_OK = False


# ---------------------------- 곤충 데이터 ----------------------------
BASE_INSECTS = {
    "ladybug":   {"name": "무당벌레",   "emoji": "🐞", "desc": "풀숲과 정원에서 흔히 보이며 진딧물을 먹어요."},
    "butterfly": {"name": "나비",     "emoji": "🦋", "desc": "꽃 근처에서 활동하며 낮에 활발히 날아요."},
    "stag":      {"name": "사슴벌레",   "emoji": "🪲", "desc": "참나무 수액 근처에 모여요. 큰 집게가 특징."},
    "rhino":     {"name": "풍뎅이",    "emoji": "🪲", "desc": "뿔 달린 딱정벌레. 밤에 불빛에 끌리기도 해요."},
    "firefly":   {"name": "반딧불이",   "emoji": "✨", "desc": "어두운 곳에서 빛을 내요. 초여름 밤에 활동적이에요."},
}
# 낮/밤 등장 곤충 세트 (ID는 BASE_INSECTS의 id와 동일)
DAY_INSECTS   = ["ladybug", "butterfly"]          # 낮: 무당벌레, 나비
NIGHT_INSECTS = ["rhino", "stag", "firefly"]      # 밤: 사슴벌레(=rhino), 장수풍뎅이(=stag), 반딧불이

INSECT_INFO = {
    "ladybug": {
        "intro": "작고 귀여운 얼굴로 해충을 물리치는 정원 히어로!",
        "detail": {
            "🧭 특징": "빨간 딱지날개와 검은 점무늬",
            "🌱 서식지": "정원, 농경지, 꽃 주변",
            "⏰ 활동 시간": "낮",
            "🍽 먹이": "진딧물 같은 식물 해충(천적 곤충)",
            "🛡 역할": "작물 보호, 생태계 균형 유지"
        }
    },
    "butterfly": {
        "intro": "꽃과 바람을 타고 춤추며 다니는 화려한 여행가!",
        "detail": {
            "🧭 특징": "다양한 색과 무늬의 날개",
            "🐛 성장": "애벌레 → 번데기 → 성충 (완전변태)",
            "🌸 서식지": "꽃이 많은 들판, 공원, 숲 가장자리",
            "🍽 먹이": "꽃꿀(애벌레는 식물 잎)",
            "✈ 역할": "꽃가루를 옮기는 자연의 배달부"
        }
    },
    "stag": {
        "intro": "멋진 큰 턱으로 싸움도 잘하고 멋도 아는 숲 속 왕자!",
        "detail": {
            "🧭 특징": "큰 턱(만디블), 광택 있는 검은 몸",
            "🌳 서식지": "오래된 나무가 많은 숲",
            "⏰ 활동 시간": "주로 밤",
            "🍽 먹이": "수액, 과일즙",
            "📌 성장": "썩은 나무 속에서 1~2년 유충 생활"
        }
    },
    "rhino": {
        "intro": "나만의 뿔을 자랑하는 숲 속의 힘센 카리스마!",
        "detail": {
            "🧭 특징": "머리에 크고 멋진 뿔",
            "🌳 서식지": "숲, 정원, 부식토가 많은 곳",
            "🕛 활동 시간": "밤",
            "🍽 먹이": "수액, 과일즙",
            "💪 힘": "몸무게의 100배 이상을 들어올릴 정도로 강함"
        }
    },
    "firefly": {
        "intro": "어둠 속에서 반짝반짝, 자연이 만든 작은 밤의 별!",
        "detail": {
            "🧭 특징": "배 끝부분에서 빛을 냄(생물 발광)",
            "💡 빛의 이유": "짝을 찾거나 의사소통",
            "🌊 서식지": "깨끗한 하천, 논 주변",
            "⏰ 활동 시간": "밤",
            "🪱 유충": "달팽이·우렁이 같은 연체동물 포식"
        }
    }
}


def render_dex():
    st.subheader(f"📚 내 도감 ({len(st.session_state.dex)})")
    if not st.session_state.dex:
        st.caption("아직 수집된 곤충이 없습니다.")
    else:
        cols = st.columns(4)
        for i, entry in enumerate(st.session_state.dex):
            info = BASE_INSECTS[entry["id"]]
            img = st.session_state.insect_imgs.get(entry["id"])
            with cols[i % 4]:
                if img:
                    st.image(img, use_container_width=True)
                st.markdown(f"### {info['emoji']} {info['name']}")
                st.caption(f"{entry['spot']} · {entry['ts']}")

# 기본 이미지 폴더 경로
ASSET_DIR = Path(__file__).parent / "images"

# 확장자 자동 탐색 (png/jpg/jpeg/webp 모두 허용)
def find_image_file(basename: str):
    exts = [".png", ".PNG", ".jpg", ".JPG", ".jpeg", ".JPEG", ".webp", ".WEBP"]
    for ext in exts:
        p = ASSET_DIR / f"{basename}{ext}"
        if p.exists():
            return p
    return None

def load_default_images():
    mapping = {
        "ladybug": "ladybug",
        "butterfly": "butterfly",
        "stag": "stag",
        "rhino": "rhino",
        "firefly": "firefly",
    }
    imgs = {}
    for iid, base in mapping.items():
        p = find_image_file(base)
        if p:
            try:
                imgs[iid] = Image.open(p).convert("RGBA")
            except Exception:
                pass
    return imgs

# ---------------------------- 유틸 ----------------------------
def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    to_rad = math.pi / 180.0
    dlat = (lat2 - lat1) * to_rad
    dlon = (lon2 - lon1) * to_rad
    a = math.sin(dlat/2)**2 + math.cos(lat1*to_rad) * math.cos(lat2*to_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def is_daytime(now: datetime):
    """True=낮(06:00~17:59), False=밤(18:00~05:59)"""
    return 6 <= now.hour < 18


# ---------------------------- 상태 ----------------------------
st.set_page_config(page_title="곤충 탐험", page_icon="🐞", layout="wide")

if "current" not in st.session_state:
    st.session_state.current = None
if "arrived_spots" not in st.session_state:
    st.session_state.arrived_spots = set()
if "spot_insect" not in st.session_state:
    st.session_state.spot_insect = {}  # spot_key -> insect_id
if "dex" not in st.session_state:
    st.session_state.dex = []
if "insect_imgs" not in st.session_state:
    st.session_state.insect_imgs = {}  # insect_id -> PIL.Image
if "insect_desc" not in st.session_state:
    st.session_state.insect_desc = {}  # insect_id -> str
# 기본 이미지가 있으면 세션에 채워 넣기(없으면 건너뜀)
_default_imgs = load_default_images()
for iid, im in _default_imgs.items():
    st.session_state.insect_imgs.setdefault(iid, im)
if "insect_counts" not in st.session_state:
    st.session_state.insect_counts = {iid: 0 for iid in BASE_INSECTS.keys()}

st.title("🗺️ 곤충 탐험 (시연용)")
# ✅ 사이드바 설정 메뉴 추가
with st.sidebar:
    st.markdown("### ⚙️ 설정")
    
    # 🔄 등장 횟수 초기화 버튼
    if st.button("🔄 등장 횟수 초기화", key="reset_counts"):
        st.session_state.insect_counts = {}
        st.session_state.spot_insect = {}
        st.success("등장 횟수가 초기화되었습니다! 🤗 새로 탐험해보세요!")

    # (옵션) 도감 초기화 버튼
    if st.button("🗑️ 도감 초기화", key="reset_dex"):
        st.session_state.dex = []
        st.success("도감을 초기화했습니다! 📘✨")


col_go_dex, _ = st.columns([1, 3])
with col_go_dex:
    if st.button("📚 내 도감", use_container_width=True):
        st.session_state.view_mode = "내 도감"

# 화면 분기: 탐험 / 내 도감
if st.session_state.get("view_mode", "탐험") == "내 도감":
    render_dex()
if st.button("🗺️ 탐험으로", use_container_width=True):
    st.session_state.view_mode = "탐험"
    st.rerun()

    st.stop()  # 아래 탐험용 지도/등장 코드는 건너뜀

# ---------------------------- 스팟(좌표 최신) ----------------------------
DEFAULT_SPOTS = [
    {"key": "hosp", "name": "충북대 병원",                        "lat": 36.6245,   "lon": 127.4545,   "radius": 80},
    {"key": "gate", "name": "충북대 정문",                        "lat": 36.632275,   "lon": 127.453036,   "radius": 80},
    {"key": "bio",  "name": "충북대학교 첨단바이오연구센터(S20동)", "lat": 36.628861,   "lon": 127.452371,   "radius": 80},
    {"key": "lib",  "name": "충북대 도서관",                      "lat": 36.628345,   "lon": 127.457695,   "radius": 80},
    {"key": "sb",   "name": "스타벅스 충북대점",                   "lat": 36.627559, "lon": 127.458570, "radius": 60},
]


# ---------------------------- 사이드바 ----------------------------
with st.sidebar:
    st.header("🎯 스팟 설정")
    spots = []
    for s in DEFAULT_SPOTS:
        with st.expander(s["name"]):
            lat = st.number_input(f"{s['name']} 위도",  key=f"{s['key']}_lat", value=s["lat"], format="%.6f")
            lon = st.number_input(f"{s['name']} 경도",  key=f"{s['key']}_lon", value=s["lon"], format="%.6f")
            rad = st.number_input(f"{s['name']} 반경 (m)", key=f"{s['key']}_rad", value=s["radius"], min_value=20, max_value=200, step=5)
        spots.append({"key": s["key"], "name": s["name"], "lat": lat, "lon": lon, "radius": float(rad)})

    st.divider()
    st.header("📡 실시간 위치")
    track = st.toggle("실시간 위치 추적 (브라우저 권한 필요)", value=False)
    follow = st.checkbox("지도 따라오기(내 위치 중심)", value=True)
    interval_sec = st.slider("갱신 간격(초)", 1, 10, 3)
    if track and not GEO_OK and not JS_OK:
        st.warning("실시간 위치 모듈이 없습니다. `pip install streamlit-geolocation streamlit-js-eval` 후 사용하세요.")
    elif track and AUTO_OK is False:
        st.warning("자동 새로고침 모듈 없음: `pip install streamlit-autorefresh` 를 설치하면 더 부드럽게 갱신됩니다.")

    st.divider()
    st.header("🧭 화면 전환")
    view = st.radio("보기", ["탐험", "내 도감"], index=0, key="view_mode")

    st.divider()
    st.header("🎨 곤충 이미지 & 설명 (사용자 등록)")
    for insect_id in ["ladybug", "butterfly", "stag", "rhino", "firefly"]:  # ← 반딧불이 추가
        info = BASE_INSECTS[insect_id]
        with st.expander(f"{info['emoji']} {info['name']}"):
            up = st.file_uploader(f"{info['name']} 이미지 업로드", type=["jpg","jpeg","png"], key=f"up_{insect_id}")
            if up:
                st.session_state.insect_imgs[insect_id] = Image.open(BytesIO(up.read()))
            desc = st.text_area(
                f"{info['name']} 설명",
                value=st.session_state.insect_desc.get(insect_id, info["desc"]),
                key=f"desc_{insect_id}"
            )
            st.session_state.insect_desc[insect_id] = desc

    st.divider()
if st.button("🧹 전체 초기화"):
    st.session_state.current = None
    st.session_state.arrived_spots = set()
    st.session_state.spot_insect = {}
    st.session_state.dex = []
    st.session_state.insect_counts = {iid: 0 for iid in BASE_INSECTS.keys()}  # ✅ 리셋 추가됨!
    st.toast("초기화 완료!", icon="✅")


# ---------------------------- 실시간 위치 추적 ----------------------------
raw_loc = None

if track and AUTO_OK:
    st_autorefresh(interval=interval_sec * 1000, key="geo_tick")

# 1차 수신: streamlit-geolocation
if track and GEO_OK:
    try:
        raw_loc = st_geolocation()
    except Exception:
        raw_loc = None

updated = False

if raw_loc and raw_loc.get("latitude") and raw_loc.get("longitude"):
    st.session_state.current = {
        "lat": float(raw_loc["latitude"]),
        "lon": float(raw_loc["longitude"]),
    }
    acc = raw_loc.get("accuracy")
    if acc is not None:
        st.caption(f"📍 브라우저 위치(geolocation): {raw_loc['latitude']:.6f}, {raw_loc['longitude']:.6f} · 정확도≈{acc:.0f} m")
    updated = True

# 2차 대체: JS 기반
if track and not updated and JS_OK:
    try:
        j = js_get_geolocation()
        # 일부 버전은 dict, 일부는 (lat, lon, acc) 튜플을 반환
        jlat = j.get("coords", {}).get("latitude") if isinstance(j, dict) else (j[0] if j and len(j) > 1 else None)
        jlon = j.get("coords", {}).get("longitude") if isinstance(j, dict) else (j[1] if j and len(j) > 1 else None)
        jacc = j.get("accuracy") if isinstance(j, dict) else (j[2] if j and len(j) > 2 else None)
        if jlat and jlon:
            st.session_state.current = {"lat": float(jlat), "lon": float(jlon)}
            if jacc:
                st.caption(f"📍 브라우저 위치(JS): {jlat:.6f}, {jlon:.6f} · 정확도≈{jacc:.0f} m")
            updated = True
    except Exception:
        pass

if track and not updated:
    st.info("위치 권한을 허용했는지 확인하세요. (허용 후 1~2회 갱신 필요 / 실내·유선 연결 시 수신 지연 가능)")


# ---------------------------- 지도 ----------------------------
if st.session_state.current and follow:
    center_lat = st.session_state.current["lat"]
    center_lon = st.session_state.current["lon"]
else:
    center_lat = spots[0]["lat"]
    center_lon = spots[0]["lon"]

m = folium.Map(location=[center_lat, center_lon], zoom_start=16, control_scale=True)

for s in spots:
    folium.Marker([s["lat"], s["lon"]], tooltip=s["name"], icon=folium.Icon(color="red", icon="flag")).add_to(m)
    folium.Circle([s["lat"], s["lon"]], radius=s["radius"], color="#FF5252", weight=2, fill=True, fill_opacity=0.15).add_to(m)

if st.session_state.current:
    c = st.session_state.current
    folium.Marker([c["lat"], c["lon"]], tooltip="현재 위치", icon=folium.Icon(color="blue", icon="user")).add_to(m)

map_data = st_folium(m, height=560)
if map_data and map_data.get("last_clicked"):
    click = map_data["last_clicked"]
    st.session_state.current = {"lat": click["lat"], "lon": click["lng"]}
    st.info(f"📍 현재 위치 설정: {click['lat']:.6f}, {click['lng']:.6f}")

if track and st.session_state.current:
    st.caption(f"⏱️ 실시간 추적 ON · {interval_sec}초마다 갱신")


# ====================== 필요 모듈/헬퍼 ======================
from datetime import datetime, time
import math, random
import streamlit as st

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon/2)**2)
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def is_daytime(now=None):
    now = (now or datetime.now()).time()
    return time(6, 0) <= now <= time(17, 59)

# (예시) 낮/밤 등장 풀 – ID는 프로젝트에 맞게 유지
DAY_POOL   = ["ladybug", "butterfly", "rhino", "stag"]
NIGHT_POOL = ["firefly", "stag", "rhino"]

# 세션 키 초기화
st.session_state.setdefault("spot_insect", {})     # {spot_key: insect_id or None}
st.session_state.setdefault("insect_counts", {})   # {insect_id: count}
st.session_state.setdefault("dex", [])             # 수집 도감


# ====================== ① 곤충 표시 함수 (항상 위에!) ======================
def render_insect(spot_key: str, spot_name: str):
    """스팟에 배정된 곤충을 화면에 표시 + 수집 버튼"""
    insect_id = st.session_state.spot_insect.get(spot_key)
    if not insect_id:
        # 배정이 없으면 아무것도 안 그림
        return

    # 아래 두 딕셔너리는 파일 상단/글로벌에 이미 정의되어 있다고 가정
    info = BASE_INSECTS[insect_id]  # {"name":..,"emoji":..,"desc":..}
    img  = st.session_state.insect_imgs.get(insect_id)
    desc = st.session_state.insect_desc.get(insect_id, info.get("desc", ""))

    st.success(f"✅ '{spot_name}' 에 도달했습니다!")

    col1, col2 = st.columns([1.2, 1], vertical_alignment="center")

    with col1:
        if img:
            st.image(img, use_container_width=True)
        else:
            st.markdown(f"## {info['emoji']} {info['name']}")

        # 정보카드(공통)
        info_card = INSECT_INFO.get(insect_id)
        if info_card:
            st.markdown(
                f"### {BASE_INSECTS[insect_id]['emoji']} "
                f"{BASE_INSECTS[insect_id]['name']}"
            )
            st.write(f"**{info_card['intro']}**")
            st.write("---")
            for k, v in info_card["detail"].items():
                st.write(f"**{k}** : {v}")

        # 수집 버튼 (중복 방지)
        if st.button(f"🎒 수집하기 ({info['name']})", key=f"cap_{spot_key}"):
            if not any(d["id"] == insect_id and d["spot"] == spot_name
                       for d in st.session_state.dex):
                st.session_state.dex.append({
                    "id": insect_id,
                    "spot": spot_name,
                    "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
                st.toast(f"{info['name']} 수집 완료!", icon="🪲")

    with col2:
        st.markdown("#### 📘 설명")
        st.write(desc if desc else "설명이 아직 없습니다.")


# ---------------------- 🌍 스팟 도달 체크 ----------------------
hit_spot = None

if st.session_state.current:
    clat = st.session_state.current["lat"]
    clon = st.session_state.current["lon"]

    for s in spots:
        d = haversine_m(clat, clon, s["lat"], s["lon"])
        if d <= s["radius"]:
            hit_spot = s
            break

if hit_spot:
    spot_key = hit_spot["key"]
    counts = st.session_state.insect_counts
    spot_insect = st.session_state.spot_insect.get(spot_key)
    
    # 🎯 스팟별 곤충이 아직 없으면 배정
    if spot_insect is None:
        pool = DAY_POOL if is_daytime() else NIGHT_POOL
        candidates = [iid for iid in pool if counts.get(iid, 0) < 20]
        chosen = random.choice(candidates) if candidates else None
        st.session_state.spot_insect[spot_key] = chosen

    insect_id = st.session_state.spot_insect.get(spot_key)

    # ✅ 등장 횟수 확인
    if insect_id is not None and counts.get(insect_id, 0) < 20:
        counts[insect_id] = counts.get(insect_id, 0) + 1
        render_insect(spot_key, hit_spot["name"])

    else:
        st.info("📌 이번 시간대 등장 가능한 곤충의 최대 등장 수(20회)를 모두 소진했습니다!")
        st.session_state.spot_insect[spot_key] = None  # 초기화하여 다음 스팟에서 새 배정 가능

elif st.session_state.spot_insect:
    last_key = list(st.session_state.spot_insect.keys())[-1]
    last_name = next(s["name"] for s in spots if s["key"] == last_key)
    render_insect(last_key, last_name)

else:
    st.caption("🗺 지도에서 스팟을 클릭하거나 위치 추적을 켜서 탐험을 계속해보세요!")



# ================== 🪲 곤충 표시 함수 ==================
def render_insect(spot_key, spot_name):
    insect_id = st.session_state.spot_insect.get(spot_key)
    if not insect_id:
        return
    
    info = BASE_INSECTS[insect_id]
    img = st.session_state.insect_imgs.get(insect_id)
    desc = st.session_state.insect_desc.get(insect_id, info.get("desc", ""))
    info_card = INSECT_INFO.get(insect_id)

    st.success(f"✅ '{spot_name}' 에 도달했습니다!")

    col1, col2 = st.columns([1.2,1], vertical_alignment="center")

    with col1:
        if img:
            st.image(img, use_container_width=True)
        else:
            st.markdown(f"### {info['emoji']} {info['name']}")

    with col2:
        st.markdown(f"### {info['emoji']} {info['name']}")

        if info_card:
            st.write(f"**{info_card['intro']}**")
            st.write("---")
            for k, v in info_card['detail'].items():
                st.write(f"**{k}** : {v}")
        else:
            st.write(desc)

        if st.button(f"🎒 수집하기 ({info['name']})", key=f"cap_{spot_key}_{insect_id}"):
            if not any(d["id"] == insect_id and d["spot"] == spot_name for d in st.session_state.dex):
                st.session_state.dex.append({
                    "id": insect_id,
                    "spot": spot_name,
                    "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                st.toast(f"{info['name']} 수집 완료!", icon="🪲")



# ---------------------------- 도감 ----------------------------
st.divider()
st.subheader(f"📚 내 도감 ({len(st.session_state.dex)})")
if not st.session_state.dex:
    st.caption("아직 수집된 곤충이 없습니다.")
else:
    cols = st.columns(4)
    for i, entry in enumerate(st.session_state.dex):
        info = BASE_INSECTS[entry["id"]]
        img = st.session_state.insect_imgs.get(entry["id"])
        with cols[i % 4]:
            if img:
                st.image(img, use_container_width=True)
            st.markdown(f"### {info['emoji']} {info['name']}")
            st.caption(f"{entry['spot']} · {entry['ts']}")

# ---------------------------- 진단(필요시 접기) ----------------------------
with st.expander("🔧 진단"):
    st.write("Python 경로:", sys.executable)
    st.write("모듈상태:", {"AUTORF": AUTO_OK, "GEO": GEO_OK, "JS": JS_OK})
    st.write("current:", st.session_state.get("current"))

