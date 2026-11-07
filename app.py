import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import os
import json
import re
from datetime import datetime

# 1. Configuração do Portal
st.set_page_config(page_title="Wellstyle Hub", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    div[data-testid="metric-container"] {
        background-color: #1E1E1E;
        border: 1px solid #333;
        padding: 5% 5% 5% 10%;
        border-radius: 10px;
        color: #00FFAA;
    }
    img { border-radius: 10px; box-shadow: 0 4px 8px rgba(0,255,170,0.2); }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE EXTRAÇÃO ---
def carregar_dados_tcx(pasta_base):
    dados = []
    ns = {'tcd': 'http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2'}
    if not os.path.exists(pasta_base): return pd.DataFrame()
        
    for arquivo in os.listdir(pasta_base):
        if arquivo.lower().endswith(('.tcx', '.tcx.txt')):
            try:
                tipo_bruto = re.sub(r'\d+', '', arquivo.lower().replace('.tcx.txt', '').replace('.tcx', '')).strip()
                tipo_treino = tipo_bruto.title() if tipo_bruto else "Treino Livre"
                tree = ET.parse(os.path.join(pasta_base, arquivo))
                root = tree.getroot()
                for activity in root.findall('.//tcd:Activity', ns):
                    data_id = activity.find('tcd:Id', ns).text
                    calorias = int(activity.find('tcd:Calories', ns).text)
                    lap = activity.find('tcd:Lap', ns)
                    tempo = int(lap.find('tcd:TotalTimeSeconds', ns).text) / 60 if lap is not None else 0
                    bpm = int(lap.find('tcd:HeartRateBpm', ns).text) if lap is not None else 0
                    
                    data_obj = datetime.strptime(data_id, "%Y-%m-%dT%H:%M:%S.000Z").date()
                    dados.append({'Data': data_obj, 'Tipo': tipo_treino, 'Calorias': calorias, 'Tempo_Minutos': tempo, 'BPM_Medio': bpm})
            except: continue
                
    df = pd.DataFrame(dados)
    if not df.empty:
        df = df.groupby('Data').agg({
            'Calorias': 'sum', 'Tempo_Minutos': 'sum', 'BPM_Medio': 'mean',
            'Tipo': lambda x: ' + '.join(x.unique())
        }).reset_index()
        df['Data'] = pd.to_datetime(df['Data'])
    return df

def carregar_dados_gymrats(pasta_base):
    dados = []
    if not os.path.exists(pasta_base): return pd.DataFrame()
    for arquivo in os.listdir(pasta_base):
        if arquivo.endswith('.json'):
            try:
                with open(os.path.join(pasta_base, arquivo), 'r', encoding='utf-8') as f:
                    conteudo = json.load(f)
                    lista_items = conteudo.get('messages', conteudo.get('checkins', conteudo.get('workouts', [])))
                    
                    for item in lista_items:
                        data_str = item.get('created_at', item.get('start_time', item.get('date', '')))
                        if not data_str: continue
                        data_obj = datetime.strptime(data_str[:19], "%Y-%m-%dT%H:%M:%S").date()
                        
                        meta = item.get('metadata', item.get('checkin_data', item))
                        if isinstance(meta, str):
                            try: meta = json.loads(meta)
                            except: meta = item
                            
                        calorias_gym = float(meta.get('calories', meta.get('kcal', 0)))
                        duracao_gym = float(meta.get('duration', meta.get('duration_minutes', 0)))
                        passos = int(meta.get('steps', 0))
                        
                        # Extraindo a nova métrica de distância do Gymrats (em km)
                        distancia = float(meta.get('distance', meta.get('distance_km', meta.get('distance_m', 0)/1000)))
                        
                        inicio_str = str(meta.get('start_time', meta.get('start', '')))
                        fim_str = str(meta.get('end_time', meta.get('end', '')))
                        inicio = inicio_str[11:16] if len(inicio_str) > 15 else inicio_str
                        fim = fim_str[11:16] if len(fim_str) > 15 else fim_str
                        
                        descricao = meta.get('description', item.get('content', item.get('text', '')))
                        
                        dados.append({
                            'Data': data_obj, 
                            'Mensagem': descricao,
                            'Gym_Calorias': calorias_gym,
                            'Gym_Duracao': duracao_gym,
                            'Gym_Passos': passos,
                            'Gym_Distancia': distancia,
                            'Gym_Inicio': inicio,
                            'Gym_Fim': fim
                        })
            except Exception as e: continue
            
    df = pd.DataFrame(dados)
    if not df.empty: df['Data'] = pd.to_datetime(df['Data'])
    return df

def carregar_imagens(pasta_base):
    dados = []
    padrao_data = re.compile(r'(\d{4})[-_]?(\d{2})[-_]?(\d{2})')
    pastas = [pasta_base, os.path.join(pasta_base, 'Balança'), os.path.join(pasta_base, 'Fotos')]
    for pasta in set(pastas):
        if os.path.exists(pasta):
            for arquivo in os.listdir(pasta):
                if arquivo.lower().endswith(('.png', '.jpg', '.jpeg')):
                    match = padrao_data.search(arquivo)
                    if match:
                        ano, mes, dia = match.groups()
                        try: data_obj = datetime(int(ano), int(mes), int(dia)).date()
                        except ValueError: continue
                        categoria = "Balança" if 'balan' in arquivo.lower() or 'balan' in pasta.lower() else "Físico"
                        dados.append({'Data': data_obj, 'Categoria': categoria, 'Caminho': os.path.join(pasta, arquivo)})
    df = pd.DataFrame(dados)
    if not df.empty: df['Data'] = pd.to_datetime(df['Data'])
    return df

# --- CARREGAMENTO INICIAL ---
df_treinos = carregar_dados_tcx(".")
df_gymrats = carregar_dados_gymrats(".")
df_imagens = carregar_imagens(".")

todas_datas = set()
if not df_treinos.empty: todas_datas.update(df_treinos['Data'].dt.date)
if not df_gymrats.empty: todas_datas.update(df_gymrats['Data'].dt.date)
if not df_imagens.empty: todas_datas.update(df_imagens['Data'].dt.date)

# --- FILTROS (SIDEBAR) ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2964/2964514.png", width=80)
st.sidebar.title("Filtros")
meses_pt = {1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'}

if todas_datas:
    tipo_filtro = st.sidebar.radio("Analisar por:", ["Todo o Período", "Por Ano", "Por Mês"])
    anos_disponiveis = sorted(list(set(d.year for d in todas_datas)), reverse=True)
    ano_f = None
    mes_f = None
    
    if tipo_filtro == "Por Ano":
        ano_f = st.sidebar.selectbox("Selecione o Ano", anos_disponiveis)
    elif tipo_filtro == "Por Mês":
        ano_f = st.sidebar.selectbox("Selecione o Ano", anos_dis
