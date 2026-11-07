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
                    for msg in conteudo.get('messages', []):
                        data_obj = datetime.strptime(msg.get('created_at', '')[:19], "%Y-%m-%dT%H:%M:%S").date()
                        dados.append({'Data': data_obj, 'Mensagem': msg.get('content', '')})
            except: continue
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

# --- FILTROS SIMPLIFICADOS (SIDEBAR) ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2964/2964514.png", width=80)
st.sidebar.title("Filtros")

# Dicionário para traduzir meses
meses_pt = {1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'}

if todas_datas:
    tipo_filtro = st.sidebar.radio("Analisar por:", ["Todo o Período", "Por Ano", "Por Mês"])
    
    anos_disponiveis = sorted(list(set(d.year for d in todas_datas)), reverse=True)
    
    ano_f = None
    mes_f = None
    
    if tipo_filtro == "Por Ano":
        ano_f = st.sidebar.selectbox("Selecione o Ano", anos_disponiveis)
    
    elif tipo_filtro == "Por Mês":
        ano_f = st.sidebar.selectbox("Selecione o Ano", anos_disponiveis)
        # Pega apenas os meses que têm dados naquele ano específico
        meses_do_ano = sorted(list(set(d.month for d in todas_datas if d.year == ano_f)))
        opcoes_meses = [meses_pt[m] for m in meses_do_ano]
        mes_nome = st.sidebar.selectbox("Selecione o Mês", opcoes_meses)
        # Descobre o número do mês com base no nome selecionado
        mes_f = [k for k, v in meses_pt.items() if v == mes_nome][0]

    # Aplicando o filtro escolhido nos DataFrames
    if ano_f is not None:
        if not df_treinos.empty: df_treinos = df_treinos[df_treinos['Data'].dt.year == ano_f]
        if not df_gymrats.empty: df_gymrats = df_gymrats[df_gymrats['Data'].dt.year == ano_f]
        if not df_imagens.empty: df_imagens = df_imagens[df_imagens['Data'].dt.year == ano_f]
        todas_datas = {d for d in todas_datas if d.year == ano_f}
        
    if mes_f is not None:
        if not df_treinos.empty: df_treinos = df_treinos[df_treinos['Data'].dt.month == mes_f]
        if not df_gymrats.empty: df_gymrats = df_gymrats[df_gymrats['Data'].dt.month == mes_f]
        if not df_imagens.empty: df_imagens = df_imagens[df_imagens['Data'].dt.month == mes_f]
        todas_datas = {d for d in todas_datas if d.month == mes_f}

st.title("⚡ Wellstyle Hub")
st.markdown("### Monitoramento de Hipertrofia e Performance")

# --- KPIs SUPERIORES ---
col1, col2, col3, col4, col5 = st.columns(5)
calorias = int(df_treinos['Calorias'].sum()) if not df_treinos.empty else 0
horas = int(df_treinos['Tempo_Minutos'].sum() / 60) if not df_treinos.empty else 0
dias = df_treinos['Data'].nunique() if not df_treinos.empty else 0

modalidade_top = "N/A"
if not df_treinos.empty:
    modalidade_top = df_treinos['Tipo'].mode()[0] if not df_treinos['Tipo'].mode().empty else "N/A"

col1.metric("🔥 Calorias", f"{calorias:,}".replace(',', '.'))
col2.metric("⏱️ Horas Treinadas", f"{horas}h")
col3.metric("📅 Dias Focados", f"{dias}")
col4.metric("💪 Modalidade Top", modalidade_top.split('+')[0].strip()) 
col5.metric("📸 Fotos / Check-ins", len(df_imagens) + len(df_gymrats))

st.divider()

# --- ABAS INDEPENDENTES RESTAURADAS ---
tab1, tab2, tab3, tab4 = st.tabs(["📈 Gráficos & Dashboard", "📸 Galeria (Fotos e Balança)", "📱 Diário Gymrats", "🚀 Visão 360º (Timeline)"])

with tab1:
    if not df_treinos.empty:
        st.markdown("#### Evolução de Gasto Calórico")
        st.bar_chart(df_treinos.set_index('Data')[['Calorias']], color="#FF4B4B")
        
        st.markdown("#### Frequência por Modalidade")
        contagem_tipos = df_treinos['Tipo'].value_counts()
        st.bar_chart(contagem_tipos, color="#00FFAA")
    else:
        st.info("Nenhum treino encontrado para este filtro.")

with tab2:
    if not df_imagens.empty:
        st.markdown("#### Acompanhamento Físico")
        datas_unicas = df_imagens['Data'].dt.date.unique()
        for data in sorted(datas_unicas, reverse=True):
            imgs_do_dia = df_imagens[df_imagens['Data'].dt.date == data]
            st.markdown(f"### {data.strftime('%d/%m/%Y')}")
            cols = st.columns(len(imgs_do_dia))
            for index, row in enumerate(imgs_do_dia.itertuples()):
                cols[index].image(row.Caminho, caption=row.Categoria, use_container_width=True)
            st.divider()
    else:
        st.info("Nenhuma foto encontrada para este filtro.")

with tab3:
    if not df_gymrats.empty:
        st.markdown("#### Interações e Check-ins")
        df_exibicao = df_gymrats[['Data', 'Mensagem']].copy()
        df_exibicao['Data'] = df_exibicao['Data'].dt.strftime('%d/%m/%Y')
        st.dataframe(df_exibicao, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum registro do Gymrats encontrado para este filtro.")

with tab4:
    st.markdown("#### Cruzamento Diário (Treino + Foto + Social)")
    if not todas_datas:
        st.info("Nenhum dado encontrado.")
    else:
        for data_alvo in sorted(list(todas_datas), reverse=True):
            st.markdown(f"### 📅 {data_alvo.strftime('%d/%m/%Y')}")
            
            t_dia = df_treinos[df_treinos['Data'].dt.date == data_alvo] if not df_treinos.empty else pd.DataFrame()
            g_dia = df_gymrats[df_gymrats['Data'].dt.date == data_alvo] if not df_gymrats.empty else pd.DataFrame()
            i_dia = df_imagens[df_imagens['Data'].dt.date == data_alvo] if not df_imagens.empty else pd.DataFrame()
            
            c_treino, c_foto, c_social = st.columns([1, 1.2, 1])
            
            with c_treino:
                if not t_dia.empty:
                    st.info(f"**🏋️ {t_dia.iloc[0]['Tipo']}**\n\n🔥 {int(t_dia.iloc[0]['Calorias'])} kcal\n\n⏱️ {int(t_dia.iloc[0]['Tempo_Minutos'])} min\n\n❤️ {int(t_dia.iloc[0]['BPM_Medio'])} bpm med.")
                else:
                    st.write("😴 *Descanso*")
            with c_foto:
                if not i_dia.empty:
                    for img in i_dia.itertuples():
                        st.image(img.Caminho, caption=f"{img.Categoria}", use_container_width=True)
            with c_social:
                if not g_dia.empty:
                    for msg in g_dia.itertuples():
                        st.success(f"💬 {msg.Mensagem}")
            st.divider()
