import streamlit as st
import datetime
import io
import os
import re
import sys
import locale

# --- 한글 달력 및 요일을 위한 locale 설정 ---
try:
    locale.setlocale(locale.LC_TIME, 'ko_KR.UTF-8')
except locale.Error:
    pass  # 환경에 한글 Locale이 없을 때는 무시

import numpy as np
import easyocr
from PIL import Image, ImageDraw  # ------ 추가

product_db = {
    "아삭 오이 피클": 6,
    "아삭 오이&무 피클": 6,

}

st.markdown(
    """
    <style>
    .main {background-color: #fff;}
    div.stTextInput > label, div.stDateInput > label {font-weight: bold;}
    input[data-testid="stTextInput"] {background-color: #eee;}
    .yellow-button button {
      background-color: #FFD600 !important;
      color: black !important;
      font-weight: bold;
    }
    .title {font-size:36px; font-weight:bold;}
    .big-blue {font-size:36px; font-weight:bold; color:#1976D2;}
    .big-red {font-size:36px; font-weight:bold; color:#d32f2f;}
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <style>
        section.main > div {max-width: 390px; min-width: 390px;}
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown('<div class="title">AI 일부인 검사기</div>', unsafe_allow_html=True)
st.write("")

# 세션 상태 변수 초기화
if "product_input" not in st.session_state:
    st.session_state.product_input = ""
if "auto_complete_show" not in st.session_state:
    st.session_state.auto_complete_show = False
if "selected_product_name" not in st.session_state:
    st.session_state.selected_product_name = ""
if "reset_triggered" not in st.session_state:
    st.session_state.reset_triggered = False
if "confirm_success" not in st.session_state:
    st.session_state.confirm_success = False
if "target_date_value" not in st.session_state:
    st.session_state.target_date_value = ""
if "ocr_result" not in st.session_state:
    st.session_state.ocr_result = None

# EasyOCR Reader (캐시: Streamlit 재실행 시 매번 모델 로딩 방지)
@st.cache_resource
def get_easyocr_reader():
    # 한국어+영어(숫자 포함) 인식
    return easyocr.Reader(['ko', 'en'], gpu=False)

def reset_all():
    st.session_state.product_input = ""
    st.session_state.selected_product_name = ""
    st.session_state.date_input = None
    st.session_state.auto_complete_show = False
    st.session_state.reset_triggered = True
    st.session_state.confirm_success = False
    st.session_state.target_date_value = ""
    st.session_state.ocr_result = None

# --- 제품명 입력과 자동완성 ---
st.write("제품명을 입력하세요")

def on_change_input():
    st.session_state.auto_complete_show = True
    st.session_state.selected_product_name = ""

product_input = st.text_input(
    "제품명",
    value=st.session_state.product_input,
    key="product_input",
    on_change=on_change_input,
    label_visibility="collapsed"
)

input_value = st.session_state.product_input
matching_products = [
    name for name in product_db.keys()
    if input_value.strip() and input_value.strip() in name
]

def select_product(name):
    st.session_state.product_input = name
    st.session_state.selected_product_name = name
    st.session_state.auto_complete_show = False

if input_value.strip() and st.session_state.auto_complete_show:
    st.write("입력한 내용과 일치하는 제품명:")
    st.markdown("""
    <style>
        .scroll-list {
            max-height: 180px;
            overflow-y: auto;
            border:1px solid #ddd;
            padding:5px;
            margin-bottom:5px;
        }
    </style>
    """, unsafe_allow_html=True)
    st.markdown('<div class="scroll-list">', unsafe_allow_html=True)
    for name in matching_products:
        col1, col2 = st.columns([8, 1])
        col1.button(
            name,
            key=f"btn_{name}",
            on_click=select_product,
            args=(name,),
            use_container_width=True
        )
        col2.write("")
    st.markdown('</div>', unsafe_allow_html=True)
elif not input_value.strip():
    st.session_state.selected_product_name = ""
    st.session_state.auto_complete_show = False

# --- 제조일자 입력 ---
st.write("제조일자")
date_input = st.date_input(
    "제조일자",
    key="date_input",
    format="YYYY.MM.DD",
    label_visibility="collapsed"
)

col1, col2 = st.columns([1, 1])
confirm = col1.button("확인", key="confirm", help="제품명과 제조일자를 확인합니다.", use_container_width=True)
reset = col2.button("새로고침", key="reset", on_click=reset_all, use_container_width=True)

def is_leap_year(year):
    return (year % 4 == 0) and ((year % 100 != 0) or (year % 400 == 0))

def get_last_day(year, month):
    if month in [1,3,5,7,8,10,12]: return 31
    elif month in [4,6,9,11]: return 30
    elif month == 2: return 29 if is_leap_year(year) else 28
    else: return 30

def get_target_date(start_date, months):
    y, m, d = start_date.year, start_date.month, start_date.day
    new_month = m + months
    new_year = y + (new_month - 1) // 12
    new_month = ((new_month - 1) % 12) + 1
    last_day = get_last_day(new_year, new_month)
    if d <= last_day:
        if d == 1:
            return datetime.date(new_year, new_month, 1)
        else:
            return datetime.date(new_year, new_month, d-1)
    else:
        return datetime.date(new_year, new_month, last_day)

if confirm:
    pname = st.session_state.product_input
    dt = st.session_state.date_input

    if pname not in product_db.keys():
        st.warning("제품명을 정확하게 입력하거나 목록에서 선택하세요.")
        st.session_state.confirm_success = False
    elif dt is None:
        st.warning("제조일자를 입력하세요.")
        st.session_state.confirm_success = False
    else:
        months = product_db[pname]
        target_date = get_target_date(dt, months)
        st.session_state.target_date_value = target_date.strftime('%Y.%m.%d')
        st.session_state.confirm_success = True
        st.session_state.ocr_result = None  # OCR 결과 초기화
        st.success(
            f"목표일부인: {target_date.strftime('%Y.%m.%d')}",
            icon="✅"
        )
        st.write(f"제품명: {pname}")
        st.write(f"제조일자: {dt.strftime('%Y.%m.%d')}")
        st.write(f"소비기한(개월): {months}")

if reset:
    st.experimental_rerun()

# --------- OCR 업로드 UI (목표 일부인 출력 이후에만 활성화) ---------
if st.session_state.confirm_success:
    st.markdown("---")
    st.write("## 📸 소비기한 OCR 판독")
    uploaded_file = st.file_uploader(
        "사진을 업로드하거나, 직접 촬영하세요.",
        type=["png","jpg","jpeg","bmp","webp","heic","heif","tiff","tif","gif","pdf"],
        accept_multiple_files=False,
        key="ocr_upload"
    )

    def _safe_date(year, month, day):
        try:
            return datetime.date(int(year), int(month), int(day))
        except Exception:
            return None

    def _normalize_to_yyyy_mm_dd(dt_obj):
        return dt_obj.strftime("%Y.%m.%d")

    def _extract_dates_from_text(text):
        """
        요구사항:
        - yyyy.mm.dd
        - yyyy년mm월mm일
        - dd.mm.yyyy
        위 3가지만 탐지.
        반환: datetime.date 리스트 (중복 제거)
        """
        if not text:
            return []

        t = text.replace("\n", " ").replace("\r", " ")

        candidates = []

        # 1) yyyy.mm.dd (month/day는 1&#126;2자리까지 OCR 오차 대응)
        for m in re.findall(r"\b(\d{4})\.(\d{1,2})\.(\d{1,2})\b", t):
            d = _safe_date(m[0], m[1], m[2])
            if d:
                candidates.append(d)

        # 2) yyyy년mm월mm일 (공백 허용)
        for m in re.findall(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일", t):
            d = _safe_date(m[0], m[1], m[2])
            if d:
                candidates.append(d)

        # 3) dd.mm.yyyy
        for m in re.findall(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", t):
            d = _safe_date(m[2], m[1], m[0])  # year=group3, month=group2, day=group1
            if d:
                candidates.append(d)

        # 중복 제거(날짜 객체 기준)
        uniq = sorted(list(set(candidates)))
        return uniq

    def detect_expiry_with_ocr(image_stream):
        """
        EasyOCR로 이미지 OCR 후 날짜 후보를 찾고,
        - 날짜가 1개면 그 날짜를 반환
        - 날짜가 2개면 더 나중 날짜를 소비기한으로 반환
        - 날짜가 3개 이상이면 실패(None) 처리
        반환값: (expiry_date_str, full_text, bbox)
        bbox: EasyOCR 결과 중 '선택된 소비기한'을 포함한 텍스트 박스 하나(가능한 경우)
        """
        reader = get_easyocr_reader()

        # PIL Image -> numpy
        try:
            image_stream.seek(0)
        except Exception:
            pass

        pil_img = Image.open(image_stream).convert("RGB")
        img_np = np.array(pil_img)

        # EasyOCR: [ [bbox, text, conf], ... ]
        results = reader.readtext(img_np, detail=1)

        if not results:
            return None, None, None

        # 전체 텍스트 구성
        pieces = []
        for r in results:
            if len(r) >= 2 and isinstance(r[1], str):
                pieces.append(r[1])
        full_text = " ".join(pieces).replace("\n", " ").replace("\r", " ")

        # 날짜 후보 추출
        dates = _extract_dates_from_text(full_text)

        if len(dates) == 0:
            return None, full_text, None
        if len(dates) >= 3:
            # 요구사항: 3개 이상이면 실패 처리
            return None, full_text, None

        # 1개 또는 2개
        if len(dates) == 1:
            expiry_dt = dates[0]
        else:
            expiry_dt = max(dates)  # 더 나중 날짜 = 소비기한

        expiry_date_str = _normalize_to_yyyy_mm_dd(expiry_dt)

        # bbox 추정: OCR 결과 중 expiry_date_str(또는 원문 형태)를 포함한 텍스트 박스를 찾음
        bbox = None

        class Vertex:
            def __init__(self, x, y):
                self.x = int(x)
                self.y = int(y)

        # 매칭 가능한 텍스트 변형들
        y = expiry_dt.year
        m = expiry_dt.month
        d = expiry_dt.day
        variants = set([
            f"{y}.{m:02d}.{d:02d}",
            f"{y}.{m}.{d}",
            f"{y}년{m:02d}월{d:02d}일",
            f"{y}년{m}월{d}일",
            f"{d:02d}.{m:02d}.{y}",
            f"{d}.{m}.{y}",
        ])

        for r in results:
            if len(r) < 2:
                continue
            text = r[1] if isinstance(r[1], str) else ""
            if not text:
                continue

            norm_text = text.replace(" ", "")
            hit = False
            for v in variants:
                if v.replace(" ", "") in norm_text:
                    hit = True
                    break

            if hit:
                pts = r[0]
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                minx, maxx = min(xs), max(xs)
                miny, maxy = min(ys), max(ys)
                bbox = [Vertex(minx, miny), Vertex(maxx, miny), Vertex(maxx, maxy), Vertex(minx, maxy)]
                break

        return expiry_date_str, full_text, bbox

    # 업로드 파일이 있으면 OCR 수행
    if uploaded_file is not None:
        # 이미지는 파일로부터 메모리 버퍼를 얻어서 다시 읽어와야 함
        uploaded_file.seek(0)
        raw_image = Image.open(uploaded_file).convert("RGB")
        uploaded_file.seek(0)

        expiry, ocr_fulltext, bbox = detect_expiry_with_ocr(uploaded_file)
        st.session_state.ocr_result = expiry

        if expiry:
            st.info(f"OCR 소비기한: {expiry}")
            if bbox:
                # 빨간색 네모 박스 그리기
                img_copy = raw_image.copy()
                draw = ImageDraw.Draw(img_copy)
                box = [(v.x, v.y) for v in bbox]
                draw.line(box + [box[0]], fill=(255,0,0), width=5)
                # 적당히 리사이즈 (넓이 380px 맞춤)
                max_width = 380
                w, h = img_copy.size
                if w > max_width:
                    scale = max_width / w
                    img_copy = img_copy.resize((int(w*scale), int(h*scale)))
                st.image(img_copy, caption="인식된 소비기한 영역", use_column_width=True)
            if expiry == st.session_state.target_date_value:
                st.markdown(
                    f'<div class="big-blue">일치</div>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f'<div class="big-red">불일치</div>',
                    unsafe_allow_html=True
                )
                st.write(f"목표일부인: {st.session_state.target_date_value}")
        else:
            st.error("일부인이 인식되지 않습니다.\n\n(사진 재촬영이나 명확한 부분으로 다시 시도해 주세요.)")
            st.session_state.ocr_result = None
