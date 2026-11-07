import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import os
import json
from datetime import datetime

# 1. Configuração do Portal (Dark Mode nativo do Streamlit)
st.set_page_config(page_title="Wellstyle Hub", page_icon="⚡", layout="wide")

# CSS customizado para os Cards de KPI
st.markdown("""
    <style>
    div[data-testid="metric-container"] {
        background-color: #1E1E1E;
        border: 1px solid #333;
        padding: 5% 5% 5% 10%;
        border-radius: 10px;
        color: #00FFAA; /* Verde Cyber */
    }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ Wellstyle Hub")
st.markdown("### Monitoramento de Hipertrofia e Performance")
st.divider()

# 2. Funções de Extração de Dados
@st.cache_data
def carregar_dados_tcx(pasta_base):
    dados = []
    ns = {'tcd': 'http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2'}
    
    # Simulação da busca na pasta Xiaomi
    # Em produção, apontaremos para a pasta real ou API do Drive
    if not os.path.exists(pasta_base):
        return pd.DataFrame()
        
    for arquivo in os.listdir(pasta_base):
        if arquivo.endswith('.tcx'):
            caminho = os.path.join(pasta_base, arquivo)
            try:
                tree = ET.parse(caminho)
                root = tree.getroot()
                
                # Navegando no XML padrão da Mi Fitness
                for activity in root.findall('.//tcd:Activity', ns):
                    data_id = activity.find('tcd:Id', ns).text
                    calorias_totais = int(activity.find('tcd:Calories', ns).text)
                    
                    lap = activity.find('tcd:Lap', ns)
                    tempo_segundos = int(lap.find('tcd:TotalTimeSeconds', ns).text) if lap is not None else 0
                    bpm = int(lap.find('tcd:HeartRateBpm', ns).text) if lap is not None else 0
                    
                    # Converte string de data para objeto datetime
                    data_obj = datetime.strptime(data_id, "%Y-%m-%dT%H:%M:%S.000Z")
                    
                    dados.append({
                        'Data_Hora': data_obj,
                        'Data': data_obj.date(),
                        'Calorias': calorias_totais,
                        'Tempo_Minutos': tempo_segundos / 60,
                        'BPM_Medio': bpm
                    })
            except Exception as e:
                continue
                
    df = pd.DataFrame(dados)
    if not df.empty:
        # Agrupa treinos do mesmo dia somando calorias/tempo e tirando média do BPM
        df = df.groupby('Data').agg({
            'Calorias': 'sum',
            'Tempo_Minutos': 'sum',
            'BPM_Medio': 'mean',
            'Data_Hora': 'count' # Conta quantos treinos no dia
        }).rename(columns={'Data_Hora': 'Qtd_Treinos'}).reset_index()
        df['Data'] = pd.to_datetime(df['Data'])
        df = df.sort_values('Data')
        
    return df

# 3. Processamento e Interface
df_treinos = carregar_dados_tcx("Xiaomi") # Apontar para o diretório correto no deploy

if df_treinos.empty:
    st.info("Nenhum arquivo .tcx processado ainda. Suba a pasta 'Xiaomi' para visualizar os dados.")
else:
    # --- SEÇÃO 1: KPIs ---
    col1, col2, col3, col4 = st.columns(4)
    
    total_calorias = int(df_treinos['Calorias'].sum())
    total_horas = int(df_treinos['Tempo_Minutos'].sum() / 60)
    total_dias = df_treinos['Data'].nunique()
    bpm_max = int(df_treinos['BPM_Medio'].max())
    
    col1.metric("🔥 Calorias Derretidas", f"{total_calorias:,}".replace(',', '.'))
    col2.metric("⏱️ Horas de Foco", f"{total_horas}h")
    col3.metric("📅 Dias de Treino", f"{total_dias} dias")
    col4.metric("❤️ Pico Médio BPM", f"{bpm_max} bpm")
    
    st.divider()
    
    # --- SEÇÃO 2: Gráfico de Evolução de Esforço ---
    st.markdown("#### Evolução de Gasto Calórico Diário")
    # Prepara dados para o gráfico nativo do Streamlit
    df_chart = df_treinos.set_index('Data')[['Calorias']]
    st.bar_chart(df_chart, color="#FF4B4B") # Vermelho moderno
    
    # --- SEÇÃO 3: Raio-X Detalhado ---
    st.markdown("#### Histórico Consolidado")
    st.dataframe(
        df_treinos.style.format({
            'Calorias': '{:.0f} kcal',
            'Tempo_Minutos': '{:.0f} min',
            'BPM_Medio': '{:.0f} bpm'
        }),
        use_container_width=True,
        hide_index=True
    )
