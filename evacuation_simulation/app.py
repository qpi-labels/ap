import streamlit as st
import networkx as nx
import matplotlib.pyplot as plt
from simulation import create_building_graph, run_evacuation_simulation
import pandas as pd

st.set_page_config(page_title="건물 내 비상 대피 시뮬레이터", layout="wide")

st.title("건물 내 비상 대피 경로 최적화 및 정체 구간 분석기")
st.write("학번: 3209 | 성명: 이재원")
st.write("화재 발생 시 피난 과정에서 발생하는 정체 구간을 분석하고, 대피 경로 최적화 알고리즘의 효과를 확인하는 시뮬레이션입니다.")

# 사이드바 설정
st.sidebar.header("설정 (Settings)")
num_people = st.sidebar.slider("시뮬레이션 인원 수", min_value=10, max_value=200, value=50, step=10)

# 세션 상태 초기화
if "control_result" not in st.session_state:
    st.session_state.control_result = None
if "experimental_result" not in st.session_state:
    st.session_state.experimental_result = None

# 1. 맵 생성 및 시각화
st.header("1. 건물 평면도 (그래프)")
graph = create_building_graph()

fig, ax = plt.subplots(figsize=(8, 4))
pos = nx.get_node_attributes(graph, 'pos')
# 노드 타입에 따라 색상 지정
colors = []
for node, data in graph.nodes(data=True):
    if data.get('type') == 'exit':
        colors.append('lightgreen')
    elif data.get('type') == 'hallway':
        colors.append('lightgray')
    else:
        colors.append('lightblue')

nx.draw(graph, pos, ax=ax, with_labels=True, node_color=colors, node_size=2000, font_size=10, font_weight='bold')
edge_labels = nx.get_edge_attributes(graph, 'weight')
nx.draw_networkx_edge_labels(graph, pos, edge_labels=edge_labels, ax=ax)
st.pyplot(fig)
st.info("초록색: 출구 | 파란색: 방 | 회색: 복도/로비\n간선의 숫자는 이동 소요 시간(가중치)을 의미합니다.")

# 2. 시뮬레이션 실행
st.header("2. 대피 시뮬레이션")
if st.button("시뮬레이션 실행", type="primary"):
    with st.spinner("시뮬레이션 진행 중..."):
        # 대조군: 단순 다익스트라 최단 경로
        st.session_state.control_result = run_evacuation_simulation(graph, num_people, strategy="shortest")
        # 실험군: 정체 구간 회피 맞춤형 경로
        st.session_state.experimental_result = run_evacuation_simulation(graph, num_people, strategy="custom")
    st.success("시뮬레이션 완료!")

# 3. 결과 확인
if st.session_state.control_result and st.session_state.experimental_result:
    st.header("3. 시뮬레이션 결과")
    
    col1, col2 = st.columns(2)
    
    control = st.session_state.control_result
    exp = st.session_state.experimental_result
    
    with col1:
        st.subheader("대조군 (단순 최단 경로)")
        st.metric(label="총 대피 시간 (초)", value=f"{control['total_time']:.2f}")
        st.write(f"대피 성공 인원: {control['evacuated_count']} / {control['num_people']}")
        
    with col2:
        st.subheader("실험군 (정체 구간 회피)")
        time_diff = exp['total_time'] - control['total_time']
        st.metric(label="총 대피 시간 (초)", value=f"{exp['total_time']:.2f}", delta=f"{time_diff:.2f} 초", delta_color="inverse")
        st.write(f"대피 성공 인원: {exp['evacuated_count']} / {exp['num_people']}")

    # 차트 시각화
    chart_data = pd.DataFrame({
        "대피 방식": ["대조군 (단순 최단 경로)", "실험군 (정체 구간 회피)"],
        "총 대피 시간 (초)": [control['total_time'], exp['total_time']]
    })
    st.bar_chart(chart_data.set_index("대피 방식"))
