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
    /* Estilo para arredondar as fotos na timeline */
    img {
        border-radius: 15px;
        box-shadow: 0 4px 8px rgba(0,255,170,0.2);
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
    
    if not os.path.exists(pasta_base): return pd.DataFrame()
        
    for arquivo in os.listdir(pasta_base):
        # O pulo do gato: aceitando o arquivo original ou o renomeado pelo Android
        if arquivo.lower().endswith(('.tcx', '.tcx.txt')):
            try:
                tree = ET.parse(os.path.join(pasta_base, arquivo))
                root = tree.getroot()
                for activity in root.findall('.//tcd:Activity', ns):
                    data_id = activity.find('tcd:Id', ns).text
                    calorias_totais = int(activity.find('tcd:Calories', ns).text)
                    lap = activity.find('tcd:Lap', ns)
                    tempo_segundos = int(lap.find('tcd:TotalTimeSeconds', ns).text) if lap is not None else 0
                    bpm = int(lap.find('tcd:HeartRateBpm', ns).text) if lap is not None else 0
                    
                    data_obj = datetime.strptime(data_id, "%Y-%m-%dT%H:%M:%S.000Z")
                    dados.append({
                        'Data': data_obj.date(),
                        'Calorias': calorias_totais,
                        'Tempo_Minutos': tempo_segundos / 60,
                        'BPM_Medio': bpm
                    })
            except: continue
                
    df = pd.DataFrame(dados)
    if not df.empty:
        df = df.groupby('Data').agg({'Calorias': 'sum', 'Tempo_Minutos': 'sum', 'BPM_Medio': 'mean'}).reset_index()
        df['Data'] = pd.to_datetime(df['Data'])
    return df

@st.cache_data
def carregar_dados_gymrats(pasta_base):
    dados = []
    if not os.path.exists(pasta_base): return pd.DataFrame()
        
    for arquivo in os.listdir(pasta_base):
        if arquivo.endswith('.json'):
            try:
                with open(os.path.join(pasta_base, arquivo), 'r', encoding='utf-8') as f:
                    conteudo = json.load(f)
                    for msg in conteudo.get('messages', []):
                        data_obj = datetime.strptime(msg.get('created_at', '')[:19], "%Y-%m-%dT%H:%M:%S")
                        dados.append({
                            'Data_Hora': data_obj,
                            'Data': data_obj.date(),
                            'Mensagem': msg.get('content', ''),
                        })
            except: continue
                
    df = pd.DataFrame(dados)
    if not df.empty:
        df['Data'] = pd.to_datetime(df['Data'])
        df = df.sort_values('Data_Hora', ascending=False)
    return df

@st.cache_data
def carregar_imagens(pasta_base):
    dados = []
    # Regex para extrair formatos de data: 20260610 ou 2026-06-10
    padrao_data = re.compile(r'(\d{4})[-_]?(\d{2})[-_]?(\d{2})')
    
    pastas_alvo = [pasta_base, os.path.join(pasta_base, 'Balança'), os.path.join(pasta_base, 'Fotos')]
    
    for pasta in set(pastas_alvo):
        if os.path.exists(pasta):
            for arquivo in os.listdir(pasta):
                if arquivo.lower().endswith(('.png', '.jpg', '.jpeg')):
                    match = padrao_data.search(arquivo)
                    if match:
                        ano, mes, dia = match.groups()
                        try:
                            # Tenta criar a data. Se os números forem inválidos (ex: mês 15), ele pula.
                            data_obj = datetime(int(ano), int(mes), int(dia)).date()
                        except ValueError:
                            continue
                        
                        categoria = "Físico"
                        if 'balan' in arquivo.lower() or 'balan' in pasta.lower():
                            categoria = "Balança"
                            
                        dados.append({
                            'Data': data_obj,
                            'Categoria': categoria,
                            'Arquivo': arquivo,
                            'Caminho': os.path.join(pasta, arquivo)
                        })
                        
    df = pd.DataFrame(dados)
    if not df.empty:
        df['Data'] = pd.to_datetime(df['Data'])
        df = df.sort_values('Data', ascending=False)
    return df

# 3. Processamento
df_treinos = carregar_dados_tcx(".")
df_gymrats = carregar_dados_gymrats(".")
df_imagens = carregar_imagens(".")

# --- SEÇÃO 1: KPIs ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("🔥 Calorias Derretidas", f"{int(df_treinos['Calorias'].sum()) if not df_treinos.empty else 0:,}".replace(',', '.'))
col2.metric("⏱️ Horas de Foco", f"{int(df_treinos['Tempo_Minutos'].sum() / 60) if not df_treinos.empty else 0}h")
col3.metric("📅 Dias de Treino", f"{df_treinos['Data'].nunique() if not df_treinos.empty else 0} dias")
col4.metric("📸 Registros Visuais", f"{len(df_imagens) if not df_imagens.empty else 0}")
st.divider()

# --- SEÇÃO 2: ABAS DO PORTAL ---
tab1, tab2, tab3 = st.tabs(["📈 Evolução de Esforço", "📸 Timeline Visual (Físico & Balança)", "📱 Diário Gymrats"])

with tab1:
    if not df_treinos.empty:
        st.markdown("#### Histórico de Gasto Calórico")
        st.bar_chart(df_treinos.set_index('Data')[['Calorias']], color="#FF4B4B")

with tab2:
    if not df_imagens.empty:
        st.markdown("#### Acompanhamento de Resultados")
        st.caption("Imagens extraídas automaticamente pelas datas nos nomes dos arquivos.")
        
        # Agrupa imagens por data para colocar lado a lado (ex: Foto de corpo + Foto da balança do mesmo dia)
        datas_unicas = df_imagens['Data'].unique()
        
        for data in datas_unicas:
            imgs_do_dia = df_imagens[df_imagens['Data'] == data]
            st.markdown(f"### {pd.to_datetime(data).strftime('%d/%m/%Y')}")
            
            # Cria colunas de acordo com a quantidade de fotos no dia
            cols = st.columns(len(imgs_do_dia))
            for index, row in enumerate(imgs_do_dia.itertuples()):
                # O Streamlit renderiza a imagem com o caption
                cols[index].image(row.Caminho, caption=f"Registro: {row.Categoria}", use_container_width=True)
            st.divider()
    else:
        st.warning("Suba arquivos de imagem (.jpg, .png) com datas no nome (ex: 2026-06-10-foto.jpg) para gerar a timeline.")

with tab3:
    if not df_gymrats.empty:
        df_exibicao = df_gymrats[['Data', 'Mensagem']].copy()
        df_exibicao['Data'] = df_exibicao['Data'].dt.strftime('%d/%m/%Y')
        st.dataframe(df_exibicao, use_container_width=True, hide_index=True)
