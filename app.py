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
                    
                    lista_items = []
                    # O SEGREDO AGORA: Juntamos TODAS as gavetas do JSON de uma vez
                    if isinstance(conteudo, dict):
                        for chave in ['messages', 'checkins', 'workouts', 'activities', 'feed']:
                            if chave in conteudo and isinstance(conteudo[chave], list):
                                lista_items.extend(conteudo[chave])
                    elif isinstance(conteudo, list):
                        lista_items = conteudo
                        
                    for item in lista_items:
                        data_str = item.get('created_at', item.get('start_time', item.get('date', '')))
                        if not data_str: continue
                        data_obj = datetime.strptime(str(data_str)[:19].replace('Z',''), "%Y-%m-%dT%H:%M:%S").date()
                        
                        meta = item.get('metadata', item.get('checkin_data', item))
                        if isinstance(meta, str):
                            try: meta = json.loads(meta)
                            except: meta = item
                            
                        # Função segura para extrair números
                        def parse_num(val, tipo):
                            try: return tipo(val)
                            except: return tipo(0)

                        calorias_gym = parse_num(meta.get('calories', meta.get('kcal', meta.get('calories_burned', 0))), float)
                        duracao_gym = parse_num(meta.get('duration', meta.get('duration_minutes', meta.get('time', 0))), float)
                        passos = parse_num(meta.get('steps', meta.get('step_count', 0)), int)
                        
                        # Extrai a distância e converte para KM se vier em metros
                        distancia = parse_num(meta.get('distance', meta.get('distance_km', meta.get('distance_m', 0))), float)
                        if distancia > 100: distancia = distancia / 1000.0 
                        
                        inicio_str = str(meta.get('start_time', meta.get('started_at', '')))
                        fim_str = str(meta.get('end_time', meta.get('ended_at', '')))
                        inicio = inicio_str[11:16] if len(inicio_str) > 15 else inicio_str
                        fim = fim_str[11:16] if len(fim_str) > 15 else fim_str
                        
                        descricao = meta.get('description', meta.get('content', meta.get('text', meta.get('title', ''))))
                        
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
meses_pt = {1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho', 7: 'Jul
