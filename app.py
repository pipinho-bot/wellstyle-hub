import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import os
import json
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
    
    if not os.path.exists(pasta_base):
        return pd.DataFrame()
        
    for arquivo in os.listdir(pasta_base):
        if arquivo.endswith('.tcx'):
            caminho = os.path.join(pasta_base, arquivo)
            try:
                tree = ET.parse(caminho)
                root = tree.getroot()
                
                for activity in root.findall('.//tcd:Activity', ns):
                    data_id = activity.find('tcd:Id', ns).text
                    calorias_totais = int(activity.find('tcd:Calories', ns).text)
                    
                    lap = activity.find('tcd:Lap', ns)
                    tempo_segundos = int(lap.find('tcd:TotalTimeSeconds', ns).text) if lap is not None else 0
                    bpm = int(lap.find('tcd:HeartRateBpm', ns).text) if lap is not None else 0
                    
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
        df = df.groupby('Data').agg({
            'Calorias': 'sum',
            'Tempo_Minutos': 'sum',
            'BPM_Medio': 'mean',
            'Data_Hora': 'count'
        }).rename(columns={'Data_Hora': 'Qtd_Treinos'}).reset_index()
        df['Data'] = pd.to_datetime(df['Data'])
        df = df.sort_values('Data')
        
    return df

@st.cache_data
def carregar_dados_gymrats(pasta_base):
    dados = []
    if not os.path.exists(pasta_base):
        return pd.DataFrame()
        
    for arquivo in os.listdir(pasta_base):
        if arquivo.endswith('.json'):
            caminho = os.path.join(pasta_base, arquivo)
            try:
                with open(caminho, 'r', encoding='utf-8') as f:
                    conteudo_json = json.load(f)
                    
                    # Acessa a lista de mensagens do JSON do Gymrats
                    for msg in conteudo_json.get('messages', []):
                        # O formato de data do json tem microsegundos: "2026-10-01T11:03:02.339797Z"
                        # Vamos cortar os microsegundos para facilitar o parse
                        data_str = msg.get('created_at', '')[:19]
                        data_obj = datetime.strptime(data_str, "%Y-%m-%dT%H:%M:%S")
                        
                        dados.append({
                            'Data_Hora': data_obj,
                            'Data': data_obj.date(),
                            'Mensagem': msg.get('content', ''),
                            'Tipo': msg.get('message_type', 'text')
                        })
            except Exception as e:
                continue
                
    df = pd.DataFrame(dados)
    if not df.empty:
        df['Data'] = pd.to_datetime(df['Data'])
        # Ordena da mensagem mais recente para a mais antiga
        df = df.sort_values('Data_Hora', ascending=False)
        
    return df

# 3. Processamento e Interface
df_treinos = carregar_dados_tcx(".")
df_gymrats = carregar_dados_gymrats(".")

if df_treinos.empty and df_gymrats.empty:
    st.info("Faça o upload dos arquivos .tcx e .json para o repositório.")
else:
    # --- SEÇÃO 1: KPIs ---
    col1, col2, col3, col4 = st.columns(4)
    
    total_calorias = int(df_treinos['Calorias'].sum()) if not df_treinos.empty else 0
    total_horas = int(df_treinos['Tempo_Minutos'].sum() / 60) if not df_treinos.empty else 0
    total_dias = df_treinos['Data'].nunique() if not df_treinos.empty else 0
    total_mensagens = len(df_gymrats) if not df_gymrats.empty else 0
    
    col1.metric("🔥 Calorias Derretidas", f"{total_calorias:,}".replace(',', '.'))
    col2.metric("⏱️ Horas de Foco", f"{total_horas}h")
    col3.metric("📅 Dias de Treino", f"{total_dias} dias")
    col4.metric("💬 Interações Gymrats", f"{total_mensagens}")
    
    st.divider()
    
    # Criando Abas para organizar o visual
    tab1, tab2 = st.tabs(["📈 Evolução de Esforço (Xiaomi)", "📱 Diário Gymrats"])
    
    with tab1:
        if not df_treinos.empty:
            st.markdown("#### Evolução de Gasto Calórico Diário")
            df_chart = df_treinos.set_index('Data')[['Calorias']]
            st.bar_chart(df_chart, color="#FF4B4B")
            
            st.markdown("#### Histórico de Treinos")
            st.dataframe(
                df_treinos.style.format({
                    'Calorias': '{:.0f} kcal',
                    'Tempo_Minutos': '{:.0f} min',
                    'BPM_Medio': '{:.0f} bpm'
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("Aguardando arquivos .tcx...")

    with tab2:
        if not df_gymrats.empty:
            st.markdown("#### Últimos Registros e Check-ins")
            
            # Mostra as interações de forma mais limpa, ignorando a hora exata para focar na data e conteúdo
            df_exibicao_social = df_gymrats[['Data', 'Tipo', 'Mensagem']].copy()
            df_exibicao_social['Data'] = df_exibicao_social['Data'].dt.strftime('%d/%m/%Y')
            
            st.dataframe(
                df_exibicao_social,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("Aguardando arquivo .json do Gymrats...")
