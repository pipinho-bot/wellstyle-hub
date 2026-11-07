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
                    if isinstance(conteudo, dict):
                        # Pega de qualquer lista na raiz do JSON
                        for chave in conteudo.keys():
                            if isinstance(conteudo[chave], list):
                                lista_items.extend(conteudo[chave])
                    elif isinstance(conteudo, list):
                        lista_items = conteudo
                        
                    for item in lista_items:
                        # Ignora itens que não parecem ser o bloco principal do Workout
                        if not isinstance(item, dict) or 'created_at' not in item: continue
                        
                        data_str = item.get('occurred_at', item.get('created_at'))
                        if not data_str: continue
                        data_obj = datetime.strptime(str(data_str)[:19].replace('Z',''), "%Y-%m-%dT%H:%M:%S").date()
                        
                        def parse_num(val, tipo):
                            try: return tipo(val) if val is not None else tipo(0)
                            except: return tipo(0)

                        # Captura as métricas estruturadas que você mandou no modelo
                        titulo = item.get('title', '')
                        descricao = item.get('description', '')
                        calorias = parse_num(item.get('calories'), float)
                        passos = parse_num(item.get('steps'), int)
                        duracao = parse_num(item.get('duration'), float)
                        
                        # Distância vem em milhas. Multiplicando por 1.609 para converter em KM.
                        milhas = parse_num(item.get('distance_miles'), float)
                        distancia_km = milhas * 1.60934
                        
                        foto_url = item.get('photo_url', '')

                        dados.append({
                            'Data': data_obj, 
                            'Gym_Titulo': titulo,
                            'Gym_Descricao': descricao if descricao else '',
                            'Gym_Calorias': calorias,
                            'Gym_Duracao': duracao,
                            'Gym_Passos': passos,
                            'Gym_Distancia': distancia_km,
                            'Gym_Foto': foto_url
                        })
            except Exception as e: continue
            
    df = pd.DataFrame(dados)
    if not df.empty: 
        # Agrupa pelo dia caso haja 2 check-ins do Gymrats no mesmo dia
        df = df.groupby('Data').agg({
            'Gym_Calorias': 'sum', 'Gym_Duracao': 'sum', 'Gym_Passos': 'sum', 'Gym_Distancia': 'sum',
            'Gym_Titulo': lambda x: ' | '.join(filter(None, x.unique())),
            'Gym_Descricao': lambda x: ' | '.join(filter(None, x.unique())),
            'Gym_Foto': lambda x: next((f for f in x if f), '')
        }).reset_index()
        df['Data'] = pd.to_datetime(df['Data'])
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
        ano_f = st.sidebar.selectbox("Selecione o Ano", anos_disponiveis)
        meses_do_ano = sorted(list(set(d.month for d in todas_datas if d.year == ano_f)))
        opcoes_meses = [meses_pt[m] for m in meses_do_ano]
        mes_nome = st.sidebar.selectbox("Selecione o Mês", opcoes_meses)
        mes_f = [k for k, v in meses_pt.items() if v == mes_nome][0]

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
calorias_tcx = int(df_treinos['Calorias'].sum()) if not df_treinos.empty else 0
horas_tcx = int(df_treinos['Tempo_Minutos'].sum() / 60) if not df_treinos.empty else 0
dias_tcx = df_treinos['Data'].nunique() if not df_treinos.empty else 0
modalidade_top = df_treinos['Tipo'].mode()[0] if not df_treinos.empty and not df_treinos['Tipo'].mode().empty else "N/A"

passos_gym = int(df_gymrats['Gym_Passos'].sum()) if not df_gymrats.empty else 0
distancia_gym = float(df_gymrats['Gym_Distancia'].sum()) if not df_gymrats.empty else 0.0
total_midia = len(df_imagens)

c1, c2, c3, c4 = st.columns(4)
c1.metric("🔥 Calorias (Xiaomi)", f"{calorias_tcx:,}".replace(',', '.'))
c2.metric("⏱️ Horas (Xiaomi)", f"{horas_tcx}h")
c3.metric("📅 Dias Focados", f"{dias_tcx}")
c4.metric("💪 Modalidade Top", modalidade_top.split('+')[0].strip()) 

st.write("")
c5, c6, c7 = st.columns(3)
c5.metric("👟 Passos Totais (Gymrats)", f"{passos_gym:,}".replace(',', '.'))
c6.metric("🗺️ Distância Total (Gymrats)", f"{distancia_gym:.1f} km")
c7.metric("📸 Galeria Física (Fotos)", f"{total_midia} registros")
st.divider()

# --- ABAS ---
tab1, tab2, tab3, tab4 = st.tabs(["📈 Gráficos & Dashboard", "📸 Galeria (Fotos e Balança)", "📱 Diário Gymrats", "🚀 Visão 360º (Timeline)"])

with tab1:
    if not df_treinos.empty:
        st.markdown("#### Evolução de Gasto Calórico")
        st.bar_chart(df_treinos.set_index('Data')[['Calorias']], color="#FF4B4B")
        st.markdown("#### Frequência por Modalidade")
        st.bar_chart(df_treinos['Tipo'].value_counts(), color="#00FFAA")
    else: st.info("Nenhum treino encontrado para este filtro.")

with tab2:
    if not df_imagens.empty:
        st.markdown("#### Acompanhamento Físico")
        for data in sorted(df_imagens['Data'].dt.date.unique(), reverse=True):
            imgs_do_dia = df_imagens[df_imagens['Data'].dt.date == data]
            st.markdown(f"### {data.strftime('%d/%m/%Y')}")
            cols = st.columns(len(imgs_do_dia))
            for index, row in enumerate(imgs_do_dia.itertuples()):
                cols[index].image(row.Caminho, caption=row.Categoria, use_container_width=True)
            st.divider()
    else: st.info("Nenhuma foto encontrada.")

with tab3:
    if not df_gymrats.empty:
        st.markdown("#### Interações e Check-ins Brutos")
        df_exibicao = df_gymrats[['Data', 'Gym_Titulo', 'Gym_Descricao', 'Gym_Calorias', 'Gym_Duracao', 'Gym_Passos', 'Gym_Distancia']].copy()
        df_exibicao['Data'] = df_exibicao['Data'].dt.strftime('%d/%m/%Y')
        st.dataframe(df_exibicao, use_container_width=True, hide_index=True)
    else: st.info("Nenhum registro encontrado.")

with tab4:
    st.markdown("#### Cruzamento Diário de Alta Performance")
    if not todas_datas:
        st.info("Nenhum dado encontrado.")
    else:
        for data_alvo in sorted(list(todas_datas), reverse=True):
            st.markdown(f"### 📅 {data_alvo.strftime('%d/%m/%Y')}")
            
            t_dia = df_treinos[df_treinos['Data'].dt.date == data_alvo] if not df_treinos.empty else pd.DataFrame()
            g_dia = df_gymrats[df_gymrats['Data'].dt.date == data_alvo] if not df_gymrats.empty else pd.DataFrame()
            i_dia = df_imagens[df_imagens['Data'].dt.date == data_alvo] if not df_imagens.empty else pd.DataFrame()
            
            c_treino, c_foto, c_social = st.columns([1, 1.2, 1.5])
            
            with c_treino:
                if not t_dia.empty:
                    st.info(f"**⌚ Sensor Xiaomi ({t_dia.iloc[0]['Tipo']})**\n\n🔥 {int(t_dia.iloc[0]['Calorias'])} kcal\n\n⏱️ {int(t_dia.iloc[0]['Tempo_Minutos'])} min\n\n❤️ {int(t_dia.iloc[0]['BPM_Medio'])} bpm")
                else: st.write("😴 *Sem registro Xiaomi*")
                    
            with c_foto:
                if not i_dia.empty:
                    for img in i_dia.itertuples():
                        st.image(img.Caminho, caption=f"{img.Categoria}", use_container_width=True)
                        
            with c_social:
                if not g_dia.empty:
                    for msg in g_dia.itertuples():
                        if not msg.Gym_Titulo and msg.Gym_Passos == 0 and msg.Gym_Calorias == 0: continue
                            
                        # Montando o Card do Gymrats com as novas chaves
                        texto_gym = f"**📱 {msg.Gym_Titulo if msg.Gym_Titulo else 'Check-in'}**"
                        if msg.Gym_Descricao:
                            texto_gym += f"\n\n*\"{msg.Gym_Descricao}\"*"
                        
                        tags = []
                        if msg.Gym_Calorias > 0: tags.append(f"🔥 {int(msg.Gym_Calorias)} kcal")
                        if msg.Gym_Duracao > 0: tags.append(f"⏱️ {int(msg.Gym_Duracao)} min")
                        if msg.Gym_Passos > 0: tags.append(f"👟 {int(msg.Gym_Passos)}")
                        if msg.Gym_Distancia > 0: tags.append(f"🗺️ {msg.Gym_Distancia:.1f} km")
                        
                        if tags:
                            texto_gym += f"\n\n👉 " + " | ".join(tags)
                            
                        st.success(texto_gym)
                        
                        # Se tiver postado foto no app (photo_url), renderiza também!
                        if msg.Gym_Foto:
                            st.image(msg.Gym_Foto, caption="Foto do Check-in", use_container_width=True)
            st.divider()
