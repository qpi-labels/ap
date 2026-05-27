import networkx as nx
import simpy
import random
import matplotlib.pyplot as plt

def create_building_graph():
    """
    건물의 기본 평면도를 NetworkX 그래프로 생성합니다.
    각 노드는 방, 복도, 또는 출구를 의미합니다.
    """
    G = nx.Graph()
    # 노드 추가 (이름, 타입, 수용 인원)
    nodes = {
        'Room1': {'type': 'room', 'capacity': 50, 'pos': (0, 2)},
        'Room2': {'type': 'room', 'capacity': 50, 'pos': (0, 1)},
        'Room3': {'type': 'room', 'capacity': 50, 'pos': (0, 0)},
        'Hallway1': {'type': 'hallway', 'capacity': 20, 'pos': (1, 2)},
        'Hallway2': {'type': 'hallway', 'capacity': 20, 'pos': (1, 1)},
        'Hallway3': {'type': 'hallway', 'capacity': 20, 'pos': (1, 0)},
        'MainHall': {'type': 'hallway', 'capacity': 30, 'pos': (2, 1)},
        'Exit1': {'type': 'exit', 'capacity': 100, 'pos': (3, 2)},
        'Exit2': {'type': 'exit', 'capacity': 100, 'pos': (3, 0)}
    }
    
    for node, attrs in nodes.items():
        G.add_node(node, **attrs)
        
    # 엣지 추가 (연결된 노드, 거리/가중치)
    edges = [
        ('Room1', 'Hallway1', 1),
        ('Room2', 'Hallway2', 1),
        ('Room3', 'Hallway3', 1),
        ('Hallway1', 'Hallway2', 1),
        ('Hallway2', 'Hallway3', 1),
        ('Hallway1', 'MainHall', 1.5),
        ('Hallway2', 'MainHall', 1),
        ('Hallway3', 'MainHall', 1.5),
        ('MainHall', 'Exit1', 2),
        ('MainHall', 'Exit2', 2),
        ('Hallway1', 'Exit1', 2.5), # 보조 통로
        ('Hallway3', 'Exit2', 2.5)  # 보조 통로
    ]
    
    for u, v, w in edges:
        G.add_edge(u, v, weight=w)
        
    return G

class Person:
    def __init__(self, env, name, graph, start_node, strategy="shortest", node_resources=None, exits=None):
        self.env = env
        self.name = name
        self.graph = graph
        self.current_node = start_node
        self.strategy = strategy
        self.node_resources = node_resources
        self.exits = exits
        self.path = []
        self.evacuated = False
        self.action = env.process(self.run())

    def run(self):
        # 목적지(출구)들 중 하나를 선택
        if self.strategy == "shortest":
            # 정적 다익스트라: 가장 가까운 출구와 경로 계산
            target_exit, path = self.find_shortest_path_to_exit(weight='weight')
        elif self.strategy == "custom":
            # 동적 가중치 또는 정체 회피 알고리즘: 각 노드의 현재 사용량(정체도)을 반영하여 경로 계산
            target_exit, path = self.find_dynamic_path_to_exit()
        else:
            path = []

        self.path = path

        # 경로를 따라 이동
        # path[0]은 현재 위치일 수 있으므로 제외
        if len(path) > 0 and path[0] == self.current_node:
            path = path[1:]

        for next_node in path:
            # 다음 노드로 이동하기 위해 리소스 요청 (병목 시뮬레이션)
            with self.node_resources[next_node].request() as req:
                yield req
                # 이동 시간 시뮬레이션 (엣지의 가중치 + 약간의 랜덤 지연)
                edge_weight = self.graph.edges[self.current_node, next_node]['weight']
                move_time = edge_weight + random.uniform(0.1, 0.5)
                yield self.env.timeout(move_time)
                self.current_node = next_node

        self.evacuated = True

    def find_shortest_path_to_exit(self, weight='weight'):
        best_path = None
        min_dist = float('inf')
        target_exit = None

        for ex in self.exits:
            try:
                dist = nx.shortest_path_length(self.graph, source=self.current_node, target=ex, weight=weight)
                if dist < min_dist:
                    min_dist = dist
                    best_path = nx.shortest_path(self.graph, source=self.current_node, target=ex, weight=weight)
                    target_exit = ex
            except nx.NetworkXNoPath:
                continue

        return target_exit, best_path

    def find_dynamic_path_to_exit(self):
        # 동적 가중치 계산: 기본 거리 + (해당 노드의 대기 인원 * 패널티)
        temp_graph = self.graph.copy()
        for u, v, d in temp_graph.edges(data=True):
            # v로 이동할 때 v의 리소스 대기 상황을 확인
            q_len = len(self.node_resources[v].queue)
            congestion_penalty = q_len * 0.5 # 1명 대기당 0.5의 비용 추가
            d['dynamic_weight'] = d['weight'] + congestion_penalty
            
        best_path = None
        min_dist = float('inf')
        target_exit = None

        for ex in self.exits:
            try:
                dist = nx.shortest_path_length(temp_graph, source=self.current_node, target=ex, weight='dynamic_weight')
                if dist < min_dist:
                    min_dist = dist
                    best_path = nx.shortest_path(temp_graph, source=self.current_node, target=ex, weight='dynamic_weight')
                    target_exit = ex
            except nx.NetworkXNoPath:
                continue
                
        return target_exit, best_path

def run_evacuation_simulation(graph, num_people, strategy="shortest"):
    env = simpy.Environment()
    
    # 각 노드를 리소스(수용 인원)로 생성
    node_resources = {}
    for node, data in graph.nodes(data=True):
        capacity = data.get('capacity', 10)
        # 출구는 용량을 무한대로 간주 (또는 매우 크게)
        if data.get('type') == 'exit':
            capacity = 1000
        node_resources[node] = simpy.Resource(env, capacity=capacity)
        
    exits = [n for n, d in graph.nodes(data=True) if d.get('type') == 'exit']
    non_exits = [n for n, d in graph.nodes(data=True) if d.get('type') != 'exit']
    
    people = []
    for i in range(num_people):
        start_node = random.choice(non_exits)
        person = Person(env, f"Person_{i}", graph, start_node, strategy, node_resources, exits)
        people.append(person)
        
    # 시뮬레이션 실행 (최대 1000초로 제한하여 무한 루프 방지)
    env.run(until=1000)
    
    # 결과 분석
    evacuated_count = sum(1 for p in people if p.evacuated)
    total_time = env.now
    
    return {
        'total_time': total_time,
        'evacuated_count': evacuated_count,
        'num_people': num_people,
        'strategy': strategy
    }
