import streamlit as st
import os
from google.cloud import vision
import google.generativeai as genai
import re
import traceback

# Gemini API 인증 설정 (secrets.toml에서만 불러옴)
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error(f"Gemini API 인증 오류: {e}")

st.title("AI 식단 분석 & 영양제 추천 서비스")

# 성별 선택
sex = st.selectbox("성별을 선택하세요", ["남성", "여성"])

# 신장 입력 (cm)
height = st.number_input("신장을 입력하세요 (cm)", min_value=0.0, step=0.1)

# 체중 입력 (kg)
weight = st.number_input("체중을 입력하세요 (kg)", min_value=0.0, step=0.1)

# 목표 선택
goal = st.selectbox("목표를 선택하세요", ["건강한 몸", "다이어트", "보디빌딩", "체력 증진"])

# 식사 내용 입력 (선택)
meal = st.text_area("오늘 먹은 식사를 입력해주세요 (선택)")

# 이미지 업로드 (선택)
image = st.file_uploader("식사 사진이 있다면 업로드 해주세요 (선택)", type=["jpg", "jpeg", "png"])

image_labels = None
vision_key_path = st.secrets.get("GOOGLE_APPLICATION_CREDENTIALS", None)
if image is not None and vision_key_path:
    try:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = vision_key_path
        client = vision.ImageAnnotatorClient()
        content = image.read()  # 한 번만 읽기
        vision_image = vision.Image(content=content)
        response = client.label_detection(image=vision_image)
        labels = response.label_annotations
        food_keywords = ["food", "dish", "meal", "cuisine", "ingredient", "fruit", "vegetable", "meat", "salad", "noodle", "rice", "bread", "soup", "chicken", "beef", "pork", "fish", "egg"]
        image_labels = [label.description for label in labels if any(k in label.description.lower() for k in food_keywords)]
        if image_labels:
            st.write("**이미지에서 추출된 음식 관련 라벨:**", image_labels)
        else:
            st.write("음식 관련 라벨을 찾지 못했습니다.")
    except Exception as e:
        print("[이미지 분석 오류 상세 로그]")
        print(traceback.format_exc())
        st.error(f"이미지 분석 중 오류가 발생했습니다: {e}")
elif image is not None and not vision_key_path:
    st.info("Vision API 키 경로가 secrets.toml에 필요합니다.")

# 프롬프트 생성 함수
def generate_prompt(gender, height, weight, goal, meal_text, image_labels=None):
    prompt = f"""
사용자 정보:
- 성별: {gender}
- 신장: {height}cm
- 체중: {weight}kg
- 목표: {goal}

오늘의 식사:
{meal_text if meal_text else '입력 없음'}

이미지에서 인식된 음식들:
{image_labels if image_labels else '없음'}

분석 기준:
[1. 식사 요약]
[2. 주요 영양소 평가]
[3. 보완 제안 (영양제 또는 음식)]
[4. 식단 개선 포인트]
[5. 피드백 한 마디]

특히 [4]번 항목에서는 잘못된 식단 구성, 부족한 부분, 지나친 부분을 실천 가능한 수준으로 상세히 조언하고,
부족한 영양소로 인해 생길 수 있는 증상도 함께 설명해줘.
"""
    return prompt

# Gemini API 호출 함수
def ask_gemini(prompt: str):
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Gemini API 호출 중 오류가 발생했습니다: {e}")
        return None

# 분석하기 버튼 및 결과 출력
if st.button("분석하기"):
    if not st.secrets.get("GEMINI_API_KEY"):
        st.warning("Gemini API Key가 secrets.toml에 필요합니다.")
    elif not (meal or image_labels):
        st.warning("식사 내용 또는 식사 사진 중 하나는 반드시 입력해야 합니다.")
    elif sex and height > 0 and weight > 0 and goal:
        prompt = generate_prompt(sex, height, weight, goal, meal, image_labels)
        response = ask_gemini(prompt)
        if response:
            try:
                sections = re.split(r'(\[\d+\.\s.*?\])', response)
                parsed = []
                i = 1
                while i < len(sections):
                    if re.match(r'\[\d+\.\s.*?\]', sections[i]):
                        title = sections[i]
                        content = sections[i+1] if i+1 < len(sections) else ''
                        parsed.append((title, content.strip()))
                        i += 2
                    else:
                        i += 1
                if parsed:
                    for title, content in parsed:
                        with st.expander(f"{title}", expanded=True):
                            st.markdown(f"### {title}")
                            if "요약" in title:
                                st.info(content)
                            elif "영양소" in title:
                                st.success(content)
                            elif "보완" in title:
                                st.warning(content)
                            elif "개선" in title:
                                st.error(content)
                            elif "피드백" in title:
                                st.markdown(f"> {content}")
                            else:
                                st.write(content)
                            st.markdown("---")
                else:
                    st.write(response)
            except Exception as e:
                st.warning(f"응답 파싱 중 문제가 발생했습니다. 원본 응답을 표시합니다.\n\n{response}")
    else:
        st.warning("성별, 신장, 체중, 목표를 모두 입력해 주세요.")
